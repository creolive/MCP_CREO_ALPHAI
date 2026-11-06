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

import json
import shutil
import subprocess
import tempfile
import unittest
from contextlib import contextmanager
from pathlib import Path
from unittest.mock import patch

import bridge
import generic_bridge as general
import server
from creo_mechdog.model_queries import RESPONSE_BUDGET
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


@contextmanager
def offline_submission_root():
    """A data root where admission succeeds but no runner/Creo work starts.

    The template only has to exist for admission; the runner spawn is replaced,
    so nothing reaches the Toolkit channel. Without a real runner pid the
    channel claim would keep blocking the next submit, so each caller clears it.
    """
    root = Path(tempfile.mkdtemp(prefix="r04_submit_"))
    template = root / "Common Files/templates/mmns_part_solid_abs.prt"
    template.parent.mkdir(parents=True)
    template.touch()
    real_root, real_jobs, real_models = bridge.ROOT, bridge.JOBS, general.MODELS
    bridge.ROOT, bridge.JOBS, general.MODELS = root, root / "jobs", root / "models"
    try:
        with (
            patch.object(bridge, "config", return_value={"creo_root": str(root)}),
            patch.object(subprocess, "Popen"),
        ):
            yield root
    finally:
        bridge.ROOT, bridge.JOBS, general.MODELS = real_root, real_jobs, real_models
        shutil.rmtree(root, ignore_errors=True)


def submit_offline(operations: list[dict]) -> dict:
    manifest = general.submit(operations)
    bridge.clear_channel_claim(manifest["job_id"])
    return manifest


async def entry_operations(entry: str, case: dict) -> list[dict]:
    """Capture the normalized operations the MCP entry hands to submit."""
    recorded: list[list[dict]] = []

    def fake_submit(operations, *args, **kwargs):
        recorded.append(operations)
        return {"job_id": "e" * 32, "operations_view": "normalized"}

    with (
        patch.object(general, "submit", side_effect=fake_submit),
        patch.object(server.startup, "require_ready"),
    ):
        if entry == "creo_extrude":
            await server.creo_extrude(
                "d" * 32,
                0,
                "solid",
                "profile",
                depth=case.get("depth"),
                mode=case.get("mode", "add"),
                depth_type=case.get("depth_type"),
            )
        else:
            await server.creo_execute_plan(
                operations=[ExtrudeOp.model_validate(extrude_op(**case))]
            )
    return recorded[0]


class SubmissionViewTests(unittest.IsolatedAsyncioTestCase):
    """R04/0.14.0: the receipt labels the plan echo as the normalized view.

    The execution defaults and the caller's request are two different views.
    ``operations_view="normalized"`` plus per-operation ``defaulted_fields`` says
    which fields the caller omitted, so an omitted depth is never restated as an
    explicit 1 mm. Both MCP entries (creo_extrude / creo_execute_plan) and both
    reads (submission receipt / full page) must agree.
    """

    CASES = (
        (
            "omitted",
            {},
            {"depth": 1, "depth_type": "blind", "defaulted_fields": ["depth", "depth_type"]},
        ),
        (
            "explicit_depth",
            {"depth": 1},
            {"depth": 1, "depth_type": "blind", "defaulted_fields": ["depth_type"]},
        ),
        (
            "through_all_omitted_depth",
            {"depth_type": "through_all", "mode": "cut"},
            {"depth": 1, "depth_type": "through_all", "defaulted_fields": ["depth"]},
        ),
        (
            "through_all_explicit_depth",
            {"depth_type": "through_all", "mode": "cut", "depth": 10},
            {"depth": 10, "depth_type": "through_all", "defaulted_fields": None},
        ),
    )

    async def test_submission_distinguishes_omitted_and_explicit_depth(self):
        for entry in ("creo_extrude", "creo_execute_plan"):
            for name, case, expected in self.CASES:
                with self.subTest(entry=entry, case=name):
                    operations = await entry_operations(entry, case)
                    self.assertEqual(len(operations), 1)
                    # The entry keeps the caller's request: an omitted field is
                    # absent here, never already defaulted.
                    for field in ("depth", "depth_type"):
                        if field in case:
                            self.assertEqual(operations[0][field], case[field])
                        else:
                            self.assertNotIn(field, operations[0])
                    with offline_submission_root():
                        receipt = submit_offline(operations)
                        self.assertEqual(receipt["operations_view"], "normalized")
                        normalized = receipt["operations"][0]
                        self.assertEqual(
                            normalized.get("defaulted_fields"), expected["defaulted_fields"]
                        )
                        self.assertEqual(normalized["depth"], expected["depth"])
                        self.assertEqual(normalized["depth_type"], expected["depth_type"])
                        # Submission, full poll and paged full read the same
                        # normalized view, so a caller cannot see two stories.
                        self.assertEqual(receipt["operations"], [normalized])
                        full = bridge.get_job(receipt["job_id"], "full")
                        self.assertEqual(full["operations_view"], "normalized")
                        self.assertEqual(full["operations"], receipt["operations"])
                        page = bridge.get_job(receipt["job_id"], "full", "operations_input")
                        self.assertEqual(page["operations_view"], "normalized")
                        self.assertEqual(page["data"]["operations_input"], receipt["operations"])

    async def test_receipt_echoes_a_35_operation_plan_inside_the_budget(self):
        with offline_submission_root():
            manifest = submit_offline([{"op": "regenerate"} for _ in range(35)])
        self.assertEqual(manifest["operations_view"], "normalized")
        self.assertEqual(len(manifest["operations"]), 35)
        self.assertEqual(manifest["operations"], validate_operations([{"op": "regenerate"}] * 35))
        encoded = len(json.dumps(manifest, ensure_ascii=False).encode("utf-8"))
        self.assertLess(encoded, RESPONSE_BUDGET)


if __name__ == "__main__":
    unittest.main()
