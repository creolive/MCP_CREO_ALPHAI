"""Public validation errors locate the problem without serializing business input."""

import asyncio
import unittest
from unittest.mock import patch

from mcp.server.mcpserver.exceptions import ToolError
from pydantic import ValidationError

import server
from creo_mechdog.schema import validate_operations


class OperationValidationMessages(unittest.TestCase):
    def message(self, operations):
        with self.assertRaises(ValidationError) as caught:
            validate_operations(operations)
        message = str(caught.exception)
        self.assertNotIn("tagged-union", message)
        self.assertNotIn("input_value", message)
        self.assertNotIn("errors.pydantic.dev", message)
        self.assertLess(len(message), 4500)
        return message

    def test_single_readonly_operation_uses_public_field(self):
        message = self.message([{"op": "mass_properties", "density_g_cm3": -1}])
        self.assertIn("density_g_cm3", message)
        self.assertIn("greater than 0", message)
        self.assertNotIn("0.mass_properties", message)

    def test_model_error_does_not_echo_operation_dict(self):
        message = self.message(
            [
                {
                    "op": "boolean_bodies",
                    "label": "secret_project",
                    "method": "union",
                    "targets": [{"kind": "body", "id": -5778}],
                    "tools": [{"kind": "body", "id": 115}],
                }
            ]
        )
        self.assertNotIn("secret_project", message)
        self.assertNotIn("'targets'", message)
        self.assertIn("negative body IDs", message)

    def test_multiple_operations_keep_indices(self):
        message = self.message(
            [
                {"op": "mass_properties", "density_g_cm3": -1},
                {"op": "mass_properties", "density_g_cm3": 0},
            ]
        )
        self.assertIn("operations[0].density_g_cm3", message)
        self.assertIn("operations[1].density_g_cm3", message)

    def test_unknown_operation_does_not_list_every_discriminator(self):
        message = self.message([{"op": "secret_unknown", "data": {"secret": "data"}}])
        self.assertIn("Unknown operation", message)
        self.assertNotIn("secret_unknown", message)
        self.assertNotIn("FeatureGroupOp", message)

    def test_missing_discriminator_and_bounded_error_count(self):
        message = self.message([{}] * 200)
        self.assertIn("op", message)
        self.assertIn("more", message)

    def test_public_mass_tool_refuses_bad_density_without_submitting(self):
        with (
            patch.object(server.general, "model_info", return_value={"model_type": "part"}),
            patch.object(
                server.general, "submit", side_effect=lambda ops, **kw: validate_operations(ops)
            ),
        ):
            with self.assertRaises(ToolError) as caught:
                asyncio.run(server.creo_get_mass_properties("b" * 32, -1))
        self.assertIn("density_g_cm3", str(caught.exception))
        self.assertNotIn("tagged-union", str(caught.exception))

    def test_execute_plan_outer_validation_keeps_schema_and_hides_input(self):
        with patch.object(server.general, "submit") as submit:
            with self.assertRaises(ToolError) as caught:
                asyncio.run(
                    server.mcp.call_tool(
                        "creo_execute_plan",
                        {
                            "operations": [
                                {
                                    "op": "boolean_bodies",
                                    "label": "secret_project",
                                    "method": "union",
                                    "targets": [{"kind": "body", "id": -1}],
                                    "tools": [{"kind": "body", "id": 2}],
                                }
                            ]
                        },
                    )
                )
        message = str(caught.exception)
        self.assertIn("operations[0]", message)
        self.assertIn("negative body IDs", message)
        self.assertNotIn("input_value", message)
        self.assertNotIn("secret_project", message)
        self.assertNotIn("errors.pydantic.dev", message)
        submit.assert_not_called()

    def test_other_tool_argument_errors_also_hide_inputs(self):
        with self.assertRaises(ToolError) as caught:
            asyncio.run(
                server.mcp.call_tool(
                    "creo_get_mass_properties", {"model_id": {"secret_project": "internal"}}
                )
            )
        message = str(caught.exception)
        self.assertIn("model_id", message)
        self.assertNotIn("secret_project", message)
        self.assertNotIn("input_value", message)
        self.assertNotIn("errors.pydantic.dev", message)

    def test_unknown_tool_error_keeps_original_behavior(self):
        with self.assertRaisesRegex(ToolError, "Unknown tool: missing_tool"):
            asyncio.run(server.mcp.call_tool("missing_tool", {}))


if __name__ == "__main__":
    unittest.main()
