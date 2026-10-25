"""BUG-083 revolve.axis input precheck, three-state semantics and dispatch rejection."""

import asyncio
import contextlib
import copy
import hashlib
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

from mcp.server.mcpserver.exceptions import ToolError
from pydantic import ValidationError

import bridge
import generic_bridge as general
import server
from creo_mechdog.references import reference_capabilities
from creo_mechdog.schema import OPERATIONS, validate_operations

ROOT = Path(__file__).resolve().parents[2]


def revolve(axis="__omitted__"):
    op = {"op": "revolve", "label": "ring", "sketch": "ring_profile", "angle": 360}
    if axis != "__omitted__":
        op["axis"] = axis
    return op


class RevolveAxisValidationTests(unittest.TestCase):
    def test_reported_structures_are_rejected_with_actionable_errors(self):
        values = [
            {"entity": "ax"},
            {},
            "ax",
            83,
            [],
            {"kind": None},
            {"kind": 123},
            {"kind": "axis"},
            {"kind": "axis", "id": -1},
            {"kind": "axis", "id": True},
            {"kind": "axis", "id": "83"},
            {"kind": "datum_axis_feature"},
            {"kind": "datum_axis_feature", "label": ""},
            {"kind": "datum_axis_feature", "label": 83},
            {"kind": "datum_plane", "axis": "z"},
            {"kind": "surface", "id": 83},
            {"kind": "datum_feature", "label": "t82_da1"},
            {"kind": "feature", "label": "t82_da1"},
            {"reference": {"kind": "axis", "id": 83}},
        ]
        for value in values:
            with self.subTest(value=value), self.assertRaises(ValueError) as caught:
                validate_operations([revolve(value)])
            message = str(caught.exception)
            self.assertIn("datum_axis_feature", message)
            self.assertIn("centerline", message)
            self.assertIn("axis_label", message)

    def test_rejection_carries_the_field_path(self):
        with self.assertRaises(ValidationError) as caught:
            OPERATIONS.validate_python([revolve({"entity": "ax"})])
        self.assertIn("axis", caught.exception.errors()[0]["loc"])

    def test_input_is_not_mutated_by_validation(self):
        reported = revolve({"kind": "datum_axis_feature", "label": "turn_axis"})
        original = copy.deepcopy(reported)
        validate_operations([reported])
        self.assertEqual(reported, original)

    def test_valid_explicit_references_are_preserved(self):
        for axis in (
            {"kind": "axis", "id": 83},
            {"kind": "axis", "id": 0},
            {"kind": "datum_axis_feature", "label": "turn_axis"},
        ):
            with self.subTest(axis=axis):
                self.assertEqual(validate_operations([revolve(axis)])[0]["axis"], axis)

    def test_omitted_and_null_use_internal_centerline_empty_object_is_rejected(self):
        omitted = validate_operations([revolve()])[0]
        self.assertNotIn("axis", omitted)
        explicit_null = validate_operations([revolve(None)])[0]
        self.assertNotIn("axis", explicit_null)
        with self.assertRaises(ValueError):
            validate_operations([revolve({})])

    def test_pattern_axis_alias_still_applies_only_to_axis_pattern(self):
        plan = [
            {
                "op": "axis_pattern",
                "label": "copies",
                "leader": "leader",
                "axis": {"kind": "datum_feature", "label": "t82_da1"},
            }
        ]
        validated = validate_operations(plan)[0]
        self.assertEqual(validated["axis"], {"kind": "datum_axis_feature", "label": "t82_da1"})

    def test_capability_examples_validate(self):
        entry = reference_capabilities()["by_tool"]["creo_revolve"]
        validate_operations([revolve(entry["axis"])])
        validate_operations([revolve(entry["axis_geometry_id"])])


class RevolveAxisSchemaTests(unittest.TestCase):
    def test_revolve_tool_schema_lists_both_axis_forms(self):
        tools = {tool.name: tool for tool in asyncio.run(server.mcp.list_tools())}
        axis = tools["creo_revolve"].input_schema["properties"]["axis"]
        selection = next(branch for branch in axis["anyOf"] if "oneOf" in branch)
        self.assertEqual(
            {form["properties"]["kind"]["const"] for form in selection["oneOf"]},
            {"axis", "datum_axis_feature"},
        )
        self.assertIn("centerline", selection["description"])
        self.assertIn("entity", selection["description"])

    def test_examples_cover_both_revolve_axis_modes(self):
        omitted = json.loads((ROOT / "examples/turned_part.json").read_text(encoding="utf-8"))
        validate_operations(omitted["operations"])
        revolves = [op for op in omitted["operations"] if op["op"] == "revolve"]
        self.assertTrue(revolves)
        for op in revolves:
            self.assertNotIn("axis", op)
        for op in omitted["operations"]:
            if op["op"] == "sketch":
                self.assertTrue(
                    any(e["type"] == "centerline" for e in op["entities"]),
                    "omitted-axis revolve sketches must contain a construction centerline",
                )

        explicit = json.loads(
            (ROOT / "examples/revolve_external_axis.json").read_text(encoding="utf-8")
        )
        validate_operations(explicit["operations"])
        kinds = [op["op"] for op in explicit["operations"]]
        self.assertLess(kinds.index("datum_axis"), kinds.index("revolve"))
        revolve_op = next(op for op in explicit["operations"] if op["op"] == "revolve")
        self.assertEqual(revolve_op["axis"], {"kind": "datum_axis_feature", "label": "turn_axis"})


class RevolveAxisQueueTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        (ROOT / ".tmp").mkdir(exist_ok=True)
        fixture = tempfile.TemporaryDirectory(prefix="bug083_", dir=ROOT / ".tmp")
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
            "aliases": {"ring_profile": {"feature_id": 41}},
        }
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

    async def queued_operation(self, tool, specific):
        self.model_file.write_text(json.dumps(self.model), encoding="utf-8")
        result = await server.mcp.call_tool(
            tool, {"model_id": self.model_id, "expected_revision": 7, **specific}
        )
        self.assertFalse(result.is_error, result)
        job_id = result.structured_content["job_id"]
        request = bridge.read_json(self.root / "jobs" / job_id / "request.json")
        return request["operations"][0]

    async def test_high_level_tool_and_execute_plan_queue_same_axis_semantics(self):
        explicit = {"kind": "datum_axis_feature", "label": "turn_axis"}
        for name, specific in (
            (
                "creo_revolve",
                {"label": "ring", "sketch": "ring_profile", "angle": 360, "axis": explicit},
            ),
            ("creo_execute_plan", {"operations": [revolve(explicit)]}),
        ):
            with self.subTest(tool=name):
                operation = await self.queued_operation(name, specific)
                self.assertEqual(operation["axis"], explicit)
        self.assertEqual(self.spawn.call_count, 2)

    async def test_omitted_and_null_tool_axis_queue_internal_centerline_revolve(self):
        for specific in (
            {"label": "ring", "sketch": "ring_profile", "angle": 360},
            {"label": "ring", "sketch": "ring_profile", "angle": 360, "axis": None},
        ):
            with self.subTest(axis=specific.get("axis", "omitted")):
                operation = await self.queued_operation("creo_revolve", specific)
                self.assertNotIn("axis", operation)
        self.assertEqual(self.spawn.call_count, 2)

    async def test_invalid_axis_rejections_do_not_create_or_launch_jobs(self):
        before = self.model_file.read_bytes()
        with self.assertRaises(ValueError):
            general.submit([revolve({"entity": "ax"})], self.model_id, expected_revision=7)
        with self.assertRaises(ValueError):
            general.submit([revolve({})], self.model_id, expected_revision=7)
        self.assertFalse((self.root / "jobs").exists())
        self.assertEqual(self.model_file.read_bytes(), before)
        self.spawn.assert_not_called()

        for tool, specific in (
            (
                "creo_revolve",
                {"label": "ring", "sketch": "ring_profile", "axis": {"entity": "ax"}},
            ),
            ("creo_execute_plan", {"operations": [revolve({"entity": "ax"})]}),
        ):
            with self.subTest(tool=tool), self.assertRaises(ToolError) as caught:
                await server.mcp.call_tool(
                    tool, {"model_id": self.model_id, "expected_revision": 7, **specific}
                )
            message = str(caught.exception)
            self.assertIn("datum_axis_feature", message)
            # The pydantic field path precedes the validator message.
            self.assertLess(message.find("axis"), message.find("Revolve axis"))
        self.spawn.assert_not_called()
        self.assertFalse((self.root / "jobs").exists())


if __name__ == "__main__":
    unittest.main()
