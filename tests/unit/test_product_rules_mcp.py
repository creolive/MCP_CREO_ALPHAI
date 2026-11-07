"""FEAT-063 public read-only planner and source distribution contracts."""

import builtins
import hashlib
import json
import os
import shutil
import socket
import subprocess
import sys
import tempfile
import unittest
from contextlib import ExitStack
from pathlib import Path
from unittest.mock import MagicMock, patch

from mcp.server.mcpserver.exceptions import ToolError
from mcp.types import CallToolRequestParams

import server
from creo_mechdog import product_rules
from tools import package

ROOT = Path(__file__).resolve().parents[2]
TOOL = "creo_plan_product_variant"
SOURCES = ("src/creo_mechdog/product_rules.py", "examples/product_rules/box_frame.json")


class ProductRulesMCPTests(unittest.IsolatedAsyncioTestCase):
    async def call(self, **arguments):
        return await server.mcp.call_tool(
            TOOL, {"template_id": "box_frame", "parameters": {}, **arguments}
        )

    async def test_registration_annotations_and_geometry(self):
        tools = {tool.name: tool for tool in await server.mcp.list_tools()}
        self.assertIn(TOOL, tools)
        self.assertEqual(tools[TOOL].annotations, server.READ)
        self.assertEqual(set(tools[TOOL].input_schema["properties"]), {"template_id", "parameters"})
        for parameters, volume in (
            ({}, 35712),
            ({"length_mm": 120, "width_mm": 80, "height_mm": 50, "wall_mm": 3}, 83508),
        ):
            result = await self.call(parameters=parameters)
            self.assertFalse(result.is_error)
            payload = result.structured_content
            self.assertEqual(payload["expected_geometry"]["volume_mm3"], volume)
            self.assertEqual(
                payload["validation"],
                {"schema": "passed", "native": "not_run", "saved_reload": "not_run"},
            )
            self.assertEqual(len(payload["plan"]["operations"]), 4)
            self.assertLessEqual(len(json.dumps(payload, ensure_ascii=False).encode()), 32768)

    async def test_uses_enabled_server_operations(self):
        with patch.dict(server.UNAVAILABLE_OPERATIONS, {"extrude": "test unavailable"}):
            result = await self.call()
        self.assertFalse(result.is_error)
        self.assertFalse(result.structured_content["executable"])
        self.assertIsNone(result.structured_content["plan"])
        self.assertEqual(
            result.structured_content["blocking_items"],
            [{"code": "missing_capability", "capability": "extrude"}],
        )
        with patch.object(server, "REGISTERED_OPERATIONS", ("sketch",)):
            result = await self.call(capability_snapshot={"operations": ["sketch", "extrude"]})
        self.assertFalse(result.structured_content["executable"])

    async def test_invalid_inputs_and_budget_are_mcp_errors(self):
        for arguments in (
            {"parameters": {"wall_mm": True}},
            {"parameters": {"wall_mm": "2"}},
            {"parameters": {"wall_mm": float("inf")}},
            {"parameters": {"wall_mm": 20, "height_mm": 10}},
            {"parameters": {"unknown": 1}},
            {"template_id": "../box_frame"},
        ):
            with self.subTest(arguments=arguments):
                with self.assertRaises(ToolError):
                    await self.call(**arguments)
                wire = await server.mcp._handle_call_tool(
                    MagicMock(),
                    CallToolRequestParams(
                        name=TOOL,
                        arguments={"template_id": "box_frame", "parameters": {}, **arguments},
                    ),
                )
                self.assertTrue(wire.is_error)
        with patch.object(product_rules, "validate_operations", return_value=[{"x": "界" * 12000}]):
            with self.assertRaisesRegex(ToolError, "32768"):
                await self.call()
            result = await server.mcp._handle_call_tool(
                MagicMock(),
                CallToolRequestParams(
                    name=TOOL, arguments={"template_id": "box_frame", "parameters": {}}
                ),
            )
        self.assertTrue(result.is_error)
        self.assertIn("32768", result.content[0].text)

    async def test_no_writes_locks_jobs_startup_connections_or_network(self):
        original_open = builtins.open

        def read_only(file, mode="r", *args, **kwargs):
            if any(flag in mode for flag in "wax+"):
                raise AssertionError("write attempted")
            return original_open(file, mode, *args, **kwargs)

        with ExitStack() as stack:
            stack.enter_context(patch("builtins.open", side_effect=read_only))
            for owner, name in (
                (Path, "write_text"),
                (Path, "write_bytes"),
                (Path, "mkdir"),
                (Path, "unlink"),
                (os, "open"),
                (subprocess, "Popen"),
                (socket.socket, "connect"),
                (server.bridge, "toolkit_lock"),
                (server.bridge, "create_job"),
                (server.general, "submit"),
                (server.startup, "require_ready"),
                (server.startup, "start"),
                (server, "creo_capabilities"),
            ):
                stack.enter_context(patch.object(owner, name, side_effect=AssertionError(name)))
            result = await self.call()
        self.assertFalse(result.is_error)
        for name in ("job_id", "model_id", "revision"):
            self.assertNotIn(name, result.structured_content)


class ProductRulesDistributionTests(unittest.TestCase):
    def test_identity_and_distribution_independent_source_copy(self):
        names = {path.relative_to(ROOT).as_posix() for path in package.source_files()}
        for name in SOURCES:
            self.assertIn(name, names)
            self.assertIn(name, server._SOURCE_NAMES)
        with tempfile.TemporaryDirectory() as directory:
            copy = Path(directory).resolve()
            for source in package.source_files():
                target = copy / source.relative_to(ROOT)
                target.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(source, target)
            code = """
import json, sys
from pathlib import Path
root = Path(sys.argv[1]).resolve()
sys.path[:0] = [str(root / 'src'), str(root)]
from creo_mechdog.paths import SOURCE_PATHS
from creo_mechdog.product_rules import build_product_plan
assert SOURCE_PATHS.resource_root == root
result = build_product_plan('box_frame', {}, {'operations': ['sketch', 'extrude']})
assert result['expected_geometry']['volume_mm3'] == 35712
print(json.dumps({'resource_root': str(SOURCE_PATHS.resource_root)}))
"""
            completed = subprocess.run(
                [sys.executable, "-B", "-c", code, str(copy)],
                cwd=copy,
                capture_output=True,
                text=True,
                check=True,
                timeout=30,
            )
            self.assertEqual(Path(json.loads(completed.stdout)["resource_root"]), copy)
            with patch.object(server, "_CODE_ROOT", copy):
                original = server._source_fingerprints()
                for name in SOURCES:
                    source = copy / name
                    data = source.read_bytes()
                    self.assertEqual(
                        original[name], hashlib.sha256(data.replace(b"\r\n", b"\n")).hexdigest()
                    )
                    source.write_bytes(data + b"\n")
                    self.assertNotEqual(server._source_fingerprints()[name], original[name])
                    source.write_bytes(data)
