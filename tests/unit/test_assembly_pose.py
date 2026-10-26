"""FEAT-012 matrix placement through the production schema and MCP registry.

Submit and readiness are substituted; no Toolkit connection or startup is made.
"""

import copy
import math
import unittest
from unittest.mock import patch

from mcp.server.mcpserver.exceptions import ToolError

import schema
import server
from creo_mechdog.schema import AssembleOp, ComponentPlacementOp, validate_operations

IDENTITY = [[1, 0, 0], [0, 1, 0], [0, 0, 1]]
Y90 = [[0, 0, -1], [0, 1, 0], [1, 0, 0]]


def operation(action="assemble_component", **values):
    identity = (
        {"label": "part", "source_model_id": "a" * 32}
        if action == "assemble_component"
        else {"component": "part"}
    )
    return {"op": action, **identity, **values}


class AssemblyPoseValidation(unittest.TestCase):
    def test_invalid_pose_rejected_before_submission_lock(self):
        for action in ("assemble_component", "component_placement"):
            with patch.object(server.bridge, "toolkit_lock") as lock:
                with self.assertRaises(ValueError):
                    server.general.submit(
                        [operation(action, rotation=[0, 0, 0], rotation_matrix=IDENTITY)],
                        "b" * 32,
                        expected_revision=1,
                    )
                lock.assert_not_called()

    def test_shared_root_export_and_euler_compatibility(self):
        self.assertIs(schema.AssembleOp, AssembleOp)
        self.assertIs(schema.ComponentPlacementOp, ComponentPlacementOp)
        for action in ("assemble_component", "component_placement"):
            for euler in (None, [0, 0, 0], [15, 90, -30]):
                values = {} if euler is None else {"rotation": euler}
                checked = validate_operations([operation(action, **values)])[0]
                self.assertEqual(checked["rotation"], euler or [0, 0, 0])
                self.assertNotIn("rotation_matrix", checked)

    def test_matrix_round_trip_without_euler_or_repair(self):
        near_identity = [[1 + 1e-7, 0, 0], [0, 1, 0], [0, 0, 1]]
        for action in ("assemble_component", "component_placement"):
            for matrix in (IDENTITY, Y90, near_identity):
                checked = validate_operations(
                    [operation(action, rotation_matrix=matrix, translation=[7, -8, 9])]
                )[0]
                self.assertEqual(checked["rotation_matrix"], matrix)
                self.assertNotIn("rotation", checked)
                self.assertEqual(checked["translation"], [7, -8, 9])

    def test_matrix_rejections_for_create_and_update(self):
        invalid = [
            [],
            [1, 0, 0, 0, 1, 0, 0, 0, 1],
            IDENTITY[:2],
            [[1, 0], [0, 1], [0, 0]],
            [[1, 0, 0, 0], [0, 1, 0], [0, 0, 1]],
            "identity",
            [[True, 0, 0], [0, 1, 0], [0, 0, 1]],
            [["1", 0, 0], [0, 1, 0], [0, 0, 1]],
            [[None, 0, 0], [0, 1, 0], [0, 0, 1]],
            [[-1, 0, 0], [0, 1, 0], [0, 0, 1]],
            [[2, 0, 0], [0, 2, 0], [0, 0, 2]],
            [[1, 1e-4, 0], [0, 1, 0], [0, 0, 1]],
            [[1 + 1e-6, 0, 0], [0, 1, 0], [0, 0, 1]],
            [[1 + 4e-7, 0, 0], [0, 1 + 4e-7, 0], [0, 0, 1 + 4e-7]],
            tuple(tuple(row) for row in IDENTITY),
            {"rows": IDENTITY},
        ]
        for value in (math.nan, math.inf, -math.inf, 1e308, 10**1000):
            matrix = copy.deepcopy(IDENTITY)
            matrix[0][0] = value
            invalid.append(matrix)
        for action in ("assemble_component", "component_placement"):
            for matrix in invalid:
                with self.subTest(action=action, matrix=matrix), self.assertRaises(ValueError):
                    validate_operations([operation(action, rotation_matrix=matrix)])
            with self.assertRaisesRegex(ValueError, "mutually exclusive"):
                validate_operations(
                    [operation(action, rotation=[0, 0, 0], rotation_matrix=IDENTITY)]
                )


class AssemblyPoseMCP(unittest.IsolatedAsyncioTestCase):
    async def test_public_registry_and_plan_paths(self):
        submitted = []

        def submit(operations, *args, **kwargs):
            checked = validate_operations(operations)
            submitted.extend(checked)
            return {"validated": checked}

        with (
            patch.object(server.general, "submit", side_effect=submit),
            patch.object(server.startup, "require_ready"),
        ):
            for tool, extra in (
                ("creo_assemble_component", {"label": "part", "source_model_id": "a" * 32}),
                ("creo_component_placement", {"component": "part"}),
            ):
                common = {
                    "model_id": "b" * 32,
                    "expected_revision": 1,
                    "translation": [2, 3, 4],
                    **extra,
                }
                for values in (
                    {},
                    {"rotation": None},
                    {"rotation": [0, 90, 0]},
                    {"rotation_matrix": Y90},
                ):
                    reply = await server.mcp.call_tool(tool, {**common, **values})
                    self.assertFalse(reply.is_error, reply)
                    checked = submitted[-1]
                    if "rotation_matrix" in values:
                        self.assertEqual(checked["rotation_matrix"], Y90)
                        self.assertNotIn("rotation", checked)
                    else:
                        self.assertEqual(checked["rotation"], values.get("rotation") or [0, 0, 0])
                for values in (
                    {"rotation": [0, 0, 0], "rotation_matrix": Y90},
                    {"rotation_matrix": [[True, 0, 0], [0, 1, 0], [0, 0, 1]]},
                    {"rotation_matrix": [["1", 0, 0], [0, 1, 0], [0, 0, 1]]},
                    {"rotation_matrix": [1] * 9},
                ):
                    count = len(submitted)
                    with self.assertRaises(ToolError):
                        await server.mcp.call_tool(tool, {**common, **values})
                    self.assertEqual(len(submitted), count)
            for action in ("assemble_component", "component_placement"):
                reply = await server.mcp.call_tool(
                    "creo_execute_plan",
                    {
                        "model_id": "b" * 32,
                        "expected_revision": 1,
                        "operations": [operation(action, rotation_matrix=Y90)],
                    },
                )
                self.assertFalse(reply.is_error, reply)
                self.assertEqual(submitted[-1]["rotation_matrix"], Y90)
                self.assertNotIn("rotation", submitted[-1])
                with self.assertRaises(ToolError):
                    await server.mcp.call_tool(
                        "creo_execute_plan",
                        {
                            "model_id": "b" * 32,
                            "expected_revision": 1,
                            "operations": [
                                operation(action, rotation=[0, 0, 0], rotation_matrix=Y90)
                            ],
                        },
                    )

    async def test_published_nested_matrix_shape(self):
        tools = {tool.name: tool for tool in await server.mcp.list_tools()}
        for name in ("creo_assemble_component", "creo_component_placement"):
            matrix = tools[name].input_schema["properties"]["rotation_matrix"]["anyOf"][0]
            self.assertEqual((matrix["minItems"], matrix["maxItems"]), (3, 3))
            self.assertEqual((matrix["items"]["minItems"], matrix["items"]["maxItems"]), (3, 3))


if __name__ == "__main__":
    unittest.main()
