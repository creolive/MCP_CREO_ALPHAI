"""W05: extruded-feature depth receipt (request vs feature-tree readback).

Offline only. The contract frozen for this block:

* ``requested_depth_type`` / ``requested_depth_mm`` are null when the caller
  omitted the field - the omission is captured before schema defaults are
  applied, never restated as 1 mm / blind;
* ``effective_depth_type`` / ``effective_depth_mm`` come from the created
  feature's own tree, and ``through_all`` never gains a fabricated blind depth;
* ``defaulted_fields`` names only depth/depth_type, and ``source`` plus
  ``query_code`` say where the values came from;
* a record without the block is left alone instead of being synthesized.
"""

import unittest

import server
from creo_mechdog.operation_results import annotate_extrude_depth, normalize_extrude_depth
from creo_mechdog.schema import ExtrudeOp, dump_plan_operations, validate_operations


def extrude_op(**overrides) -> dict:
    op = {"op": "extrude", "label": "solid", "sketch": "profile"}
    op.update(overrides)
    return op


class OmissionCaptureTests(unittest.TestCase):
    def test_omitted_depth_and_type_are_marked_before_defaults(self):
        dumped = validate_operations([extrude_op()])[0]
        self.assertEqual(dumped["depth"], 1)
        self.assertEqual(dumped["depth_type"], "blind")
        self.assertEqual(dumped["defaulted_fields"], ["depth", "depth_type"])

    def test_explicit_depth_marks_only_the_type(self):
        dumped = validate_operations([extrude_op(depth=10)])[0]
        self.assertEqual(dumped["depth"], 10)
        self.assertEqual(dumped["depth_type"], "blind")
        self.assertEqual(dumped["defaulted_fields"], ["depth_type"])

    def test_explicit_fields_carry_no_marker(self):
        dumped = validate_operations([extrude_op(depth=10, depth_type="through_all", mode="cut")])[
            0
        ]
        self.assertNotIn("defaulted_fields", dumped)

    def test_through_all_still_requires_cut_mode(self):
        with self.assertRaises(ValueError) as caught:
            validate_operations([extrude_op(depth_type="through_all")])
        self.assertIn("through_all", str(caught.exception))


class PlanEntryOmissionTests(unittest.TestCase):
    """The plan entry validates into models first; its dump must keep omission.

    creo_execute_plan used to dump the models as-is, so the defaults erased the
    omission and the live receipt read back an explicit-looking request.
    """

    def test_omitted_depth_and_type_survive_the_model_dump(self):
        model = ExtrudeOp.model_validate(extrude_op())
        revalidated = validate_operations(dump_plan_operations([model]))[0]
        self.assertEqual(revalidated["depth"], 1)
        self.assertEqual(revalidated["depth_type"], "blind")
        self.assertEqual(revalidated["defaulted_fields"], ["depth", "depth_type"])

    def test_explicit_depth_survives_the_model_dump(self):
        model = ExtrudeOp.model_validate(extrude_op(depth=10))
        dumped = dump_plan_operations([model])[0]
        self.assertEqual(dumped["depth"], 10)
        self.assertNotIn("depth_type", dumped)
        revalidated = validate_operations([dumped])[0]
        self.assertEqual(revalidated["defaulted_fields"], ["depth_type"])

    def test_explicit_fields_stay_explicit(self):
        model = ExtrudeOp.model_validate(extrude_op(depth=10, depth_type="through_all", mode="cut"))
        revalidated = validate_operations(dump_plan_operations([model]))[0]
        self.assertNotIn("defaulted_fields", revalidated)


class ReceiptNormalizationTests(unittest.TestCase):
    def test_missing_block_is_not_fabricated(self):
        result = {"operations": [{"op": "extrude", "label": "solid"}]}
        annotate_extrude_depth(result)
        self.assertNotIn("extrude_depth", result["operations"][0])

    def test_non_extrude_records_are_untouched(self):
        block = {"source": "feature_tree"}
        result = {"operations": [{"op": "revolve", "extrude_depth": block}]}
        annotate_extrude_depth(result)
        self.assertIs(result["operations"][0]["extrude_depth"], block)

    def test_omitted_request_survives_with_tree_values(self):
        entry = normalize_extrude_depth(
            {
                "source": "feature_tree",
                "query_code": 0,
                "requested_depth_type": None,
                "requested_depth_mm": None,
                "effective_depth_type": "blind",
                "effective_depth_mm": 1.0,
                "defaulted_fields": ["depth", "depth_type"],
            }
        )
        self.assertIsNone(entry["requested_depth_type"])
        self.assertIsNone(entry["requested_depth_mm"])
        self.assertEqual(entry["effective_depth_type"], "blind")
        self.assertEqual(entry["effective_depth_mm"], 1.0)
        self.assertEqual(entry["defaulted_fields"], ["depth", "depth_type"])
        self.assertEqual(entry["source"], "feature_tree")
        self.assertEqual(entry["query_code"], 0)

    def test_through_all_keeps_effective_depth_null(self):
        entry = normalize_extrude_depth(
            {
                "source": "feature_tree",
                "query_code": 0,
                "requested_depth_type": "through_all",
                "requested_depth_mm": None,
                "effective_depth_type": "through_all",
                "effective_depth_mm": None,
                "defaulted_fields": ["depth"],
            }
        )
        self.assertIsNone(entry["effective_depth_mm"])
        self.assertEqual(entry["defaulted_fields"], ["depth"])

    def test_unknown_values_are_dropped_not_coerced(self):
        entry = normalize_extrude_depth(
            {
                "source": "request",
                "query_code": "x",
                "requested_depth_type": "blind",
                "requested_depth_mm": True,
                "effective_depth_type": "mystery",
                "effective_depth_mm": "1",
                "defaulted_fields": ["mode", "depth", "mode"],
            }
        )
        self.assertEqual(entry["source"], "unknown")
        self.assertIsNone(entry["query_code"])
        self.assertIsNone(entry["requested_depth_mm"])
        self.assertIsNone(entry["effective_depth_type"])
        self.assertIsNone(entry["effective_depth_mm"])
        self.assertEqual(entry["defaulted_fields"], ["depth"])

    def test_unreadable_tree_keeps_nulls(self):
        entry = normalize_extrude_depth(
            {"source": "unknown", "query_code": -1, "defaulted_fields": []}
        )
        self.assertEqual(entry["query_code"], -1)
        self.assertIsNone(entry["requested_depth_type"])
        self.assertIsNone(entry["effective_depth_type"])
        self.assertIsNone(entry["effective_depth_mm"])


class ExtrudeToolSchemaTests(unittest.IsolatedAsyncioTestCase):
    async def test_depth_arguments_default_to_null_not_to_a_value(self):
        tools = {tool.name: tool for tool in await server.mcp.list_tools()}
        schema = tools["creo_extrude"].input_schema
        for field in ("depth", "depth_type"):
            with self.subTest(field=field):
                self.assertNotIn(field, schema.get("required", []))
                # A null default keeps the omission visible; 1 / "blind" here
                # would erase the difference the receipt has to report.
                self.assertIsNone(schema["properties"][field].get("default"))


if __name__ == "__main__":
    unittest.main()
