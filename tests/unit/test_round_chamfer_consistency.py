"""DEV-042 round/chamfer field mapping, alias rejection and result echoes."""

import asyncio
import contextlib
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
from creo_mechdog.schema import RoundOp, validate_operations

ROOT = Path(__file__).resolve().parents[2]

REFS = [{"edge": {"kind": "edge", "id": 7}}]


def operation(op, **overrides):
    base = {"op": op, "label": "edge_finish", "size": 3.0, "references": REFS}
    base.update(overrides)
    return base


class RoundChamferAliasTests(unittest.TestCase):
    def test_matching_alias_resolves_to_size_and_is_not_serialized(self):
        for op, alias in (("round", "radius"), ("chamfer", "distance")):
            with self.subTest(op=op):
                source = {"op": op, "label": "edge_finish", alias: 2.5, "references": REFS}
                original = dict(source)
                validated = validate_operations([source])
                self.assertEqual(
                    validated,
                    [{"op": op, "label": "edge_finish", "size": 2.5, "references": REFS}],
                )
                self.assertEqual(source, original)

    def test_size_only_requests_are_unchanged(self):
        for op in ("round", "chamfer"):
            with self.subTest(op=op):
                self.assertEqual(validate_operations([operation(op)])[0], operation(op))

    def test_size_and_matching_alias_together_are_rejected(self):
        for op, alias in (("round", "radius"), ("chamfer", "distance")):
            with self.subTest(op=op):
                payload = {"op": op, "label": "x", "size": 1.0, alias: 2.0, "references": REFS}
                with self.assertRaises(ValidationError) as raised:
                    RoundOp.model_validate(payload)
                self.assertIn("not both", str(raised.exception))
                with self.assertRaises(ValueError) as plan_error:
                    validate_operations([payload])
                self.assertIn("not both", str(plan_error.exception))

    def test_cross_operation_alias_is_rejected(self):
        for op, wrong in (("round", "distance"), ("chamfer", "radius")):
            with self.subTest(op=op):
                payload = {"op": op, "label": "x", wrong: 2.0, "references": REFS}
                with self.assertRaises(ValidationError) as raised:
                    RoundOp.model_validate(payload)
                self.assertIn(f"does not accept '{wrong}'", str(raised.exception))

    def test_both_aliases_or_missing_value_are_rejected(self):
        payloads = [
            {"op": "round", "label": "x", "radius": 1.0, "distance": 2.0, "references": REFS},
            {"op": "chamfer", "label": "x", "radius": 1.0, "distance": 2.0, "references": REFS},
            {"op": "round", "label": "x", "references": REFS},
            {"op": "chamfer", "label": "x", "references": REFS},
        ]
        for payload in payloads:
            with self.subTest(payload=payload):
                with self.assertRaises(ValidationError):
                    RoundOp.model_validate(payload)

    def test_execute_plan_schema_publishes_the_alias_fields(self):
        tools = {tool.name: tool for tool in asyncio.run(server.mcp.list_tools())}
        schema = tools["creo_execute_plan"].input_schema
        properties = schema["$defs"]["RoundOp"]["properties"]
        for name in ("radius", "distance", "size"):
            self.assertIn(name, properties)


class StandaloneToolMappingTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        (ROOT / ".tmp").mkdir(exist_ok=True)
        fixture = tempfile.TemporaryDirectory(prefix="dev042_", dir=ROOT / ".tmp")
        self.addCleanup(fixture.cleanup)
        self.root = Path(fixture.name).resolve()
        self.model_id = "a" * 32
        model_dir = self.root / "models" / self.model_id
        model_dir.mkdir(parents=True)
        self.model_file = model_dir / "model.json"
        output = model_dir / "output"
        output.mkdir()
        part = output / "fixture.prt.1"
        part.write_bytes(b"controlled saved baseline fixture")
        self.model = {
            "model_id": self.model_id,
            "model_name": "fixture",
            "model_type": "part",
            "status": "ready",
            "revision": 7,
            "pending_job": None,
            "aliases": {},
            "output_directory": str(output),
            "part_file": str(part),
            "part_sha256": hashlib.sha256(part.read_bytes()).hexdigest(),
        }
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
        self.enterContext(patch.object(general.subprocess, "Popen", return_value=Mock()))
        self.enterContext(patch.object(server.startup, "require_ready"))

    async def submit_and_read(self, name, arguments):
        self.model_file.write_text(json.dumps(self.model), encoding="utf-8")
        result = await server.mcp.call_tool(name, arguments)
        self.assertFalse(result.is_error, result)
        job_id = result.structured_content["job_id"]
        request = bridge.read_json(self.root / "jobs" / job_id / "request.json")
        # The queued runner would release the channel claim on completion
        # (BUG-100); payload comparison tests do the same before the next
        # submission so admission stays exercised instead of stubbed.
        bridge.clear_channel_claim(job_id)
        return result.structured_content, request["operations"]

    async def test_standalone_tools_and_execute_plan_queue_the_same_operation(self):
        inputs = {"model_id": self.model_id, "expected_revision": 7}
        references = [{"edge": {"kind": "edge", "id": 9}}]
        submitted, operations = await self.submit_and_read(
            "creo_round",
            {
                **inputs,
                "label": "fillet",
                "radius": 3.0,
                "references": references,
            },
        )
        self.assertEqual(
            operations,
            [{"op": "round", "label": "fillet", "size": 3.0, "references": references}],
        )
        self.assertEqual(submitted["operations"][0]["size"], 3.0)
        self.model_file.write_text(json.dumps(self.model), encoding="utf-8")
        _, operations = await self.submit_and_read(
            "creo_execute_plan",
            {
                **inputs,
                "operations": [
                    {"op": "round", "label": "fillet", "size": 3.0, "references": references}
                ],
            },
        )
        self.assertEqual(operations[0]["op"], "round")
        self.assertEqual(operations[0]["size"], 3.0)
        self.assertNotIn("radius", operations[0])

    async def test_execute_plan_chamfer_alias_queues_size_only_request(self):
        references = [{"edge": {"kind": "edge", "id": 4}}]
        _, operations = await self.submit_and_read(
            "creo_execute_plan",
            {
                "model_id": self.model_id,
                "expected_revision": 7,
                "operations": [
                    {
                        "op": "chamfer",
                        "label": "break_edge",
                        "distance": 1.5,
                        "references": references,
                    }
                ],
            },
        )
        self.assertEqual(
            operations,
            [{"op": "chamfer", "label": "break_edge", "size": 1.5, "references": references}],
        )

    async def test_execute_plan_alias_conflict_is_a_tool_error(self):
        with self.assertRaises(ToolError) as raised:
            await server.mcp.call_tool(
                "creo_execute_plan",
                {
                    "model_id": self.model_id,
                    "expected_revision": 7,
                    "operations": [
                        {
                            "op": "round",
                            "label": "fillet",
                            "size": 3.0,
                            "radius": 3.0,
                            "references": REFS,
                        }
                    ],
                },
            )
        self.assertIn("not both", str(raised.exception))


class CompactEchoTests(unittest.TestCase):
    def test_compact_keeps_round_and_chamfer_size_echo(self):
        manifest = {
            "job_id": "a" * 32,
            "status": "succeeded",
            "model_id": "b" * 32,
            "revision": 8,
            "operations": [{"op": "round", "label": "fillet", "size": 3.0, "references": REFS}],
            "result": {
                "success": True,
                "operations": [
                    {
                        "op": "round",
                        "label": "fillet",
                        "succeeded": True,
                        "size": 3.0,
                        "feature_id": 42,
                    },
                    {
                        "op": "chamfer",
                        "label": "break_edge",
                        "succeeded": True,
                        "size": 1.5,
                        "feature_id": 43,
                        "material_removed_mm3": 2.25,
                    },
                    {
                        "op": "sketch",
                        "label": "profile",
                        "succeeded": True,
                        "entity_ids": {"box_0": 1},
                    },
                ],
            },
        }
        compact = bridge.compact_job(manifest)
        echoed = compact["result"]["operations"]
        self.assertEqual(echoed[0]["size"], 3.0)
        self.assertEqual(echoed[1]["size"], 1.5)
        self.assertNotIn("entity_ids", echoed[2])
        self.assertNotIn("size", echoed[2])


if __name__ == "__main__":
    unittest.main()
