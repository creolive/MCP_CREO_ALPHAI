"""FEAT-008 T01: label guidance retains the existing accepted names."""

import unittest
from unittest.mock import patch

from pydantic import TypeAdapter, ValidationError

import generic_bridge
import server
from creo_mechdog.schema import Label, validate_operations


def sketch(label: str, name: str = "profile") -> dict:
    return {
        "op": "sketch",
        "label": label,
        "entities": [{"type": "circle", "name": name, "center": [0, 0], "radius": 5}],
    }


class LabelContractTests(unittest.TestCase):
    def test_valid_boundary_labels_keep_their_exact_spelling(self):
        adapter = TypeAdapter(Label)
        self.assertEqual(adapter.json_schema()["pattern"], r"^[a-z][a-z0-9_]{0,27}$")
        for value in ("a", "i001_part1", "s02_l00", "a" + "0" * 27):
            with self.subTest(value=value):
                self.assertEqual(adapter.validate_python(value), value)
                self.assertEqual(validate_operations([sketch(value)])[0]["label"], value)

    def test_non_string_label_keeps_its_type_error(self):
        with self.assertRaises(ValidationError) as caught:
            validate_operations([sketch(5)])
        errors = [error for error in caught.exception.errors() if error["loc"][-1] == "label"]
        self.assertEqual(errors[0]["type"], "string_type")

    def test_invalid_labels_explain_rule_without_silent_rename(self):
        for value in ("S02_l00", "I001_part1", "0part", "_part", "part-a", "a" * 29, "零件"):
            with self.subTest(value=value), self.assertRaises(ValidationError) as caught:
                validate_operations([sketch(value)])
            errors = [error for error in caught.exception.errors() if error["loc"][-1] == "label"]
            self.assertTrue(errors)
            self.assertEqual(errors[0]["type"], "string_pattern_mismatch")
            message = errors[0]["msg"]
            self.assertIn("28", message)
            self.assertIn("[a-z0-9_]", message)
            self.assertIn("i001_part1", message)

    def test_nested_entity_name_error_identifies_its_field(self):
        with self.assertRaises(ValidationError) as caught:
            validate_operations([sketch("part", "S02_l00")])
        matching = [
            error
            for error in caught.exception.errors()
            if error["loc"][-1] == "name" and "entities" in error["loc"]
        ]
        self.assertTrue(matching)
        self.assertIn("i001_part1", matching[0]["msg"])

    def test_invalid_label_is_rejected_before_toolkit_lock(self):
        with patch.object(generic_bridge.bridge, "toolkit_lock") as lock:
            with self.assertRaises(ValidationError):
                generic_bridge.submit([sketch("S02_l00")], "a" * 32, expected_revision=1)
        lock.assert_not_called()


class LabelPublicToolTests(unittest.IsolatedAsyncioTestCase):
    async def test_plan_tool_returns_field_path_and_rule_without_submission(self):
        from mcp.server.mcpserver.exceptions import ToolError

        with (
            patch.object(server.startup, "require_ready"),
            patch.object(server.general, "submit") as submit,
        ):
            with self.assertRaises(ToolError) as caught:
                await server.mcp.call_tool(
                    "creo_execute_plan",
                    {
                        "model_id": "a" * 32,
                        "expected_revision": 1,
                        "operations": [sketch("S02_l00")],
                    },
                )
            submit.assert_not_called()
        message = str(caught.exception)
        self.assertIn("label", message)
        self.assertIn("[a-z0-9_]", message)
        self.assertIn("i001_part1", message)
