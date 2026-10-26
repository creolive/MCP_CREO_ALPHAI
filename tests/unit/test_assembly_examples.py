"""FEAT-008 assembly example contracts stay callable against the real MCP schema."""

import json
import re
import unittest

from creo_mechdog.paths import SOURCE_PATHS
from creo_mechdog.schema import validate_operations


def load(name):
    return json.loads((SOURCE_PATHS.resource_root / "examples" / name).read_text(encoding="utf-8"))


class AssemblyExamples(unittest.TestCase):
    def test_multicomponent_plan_validates(self):
        document = load("assembly_multicomponent_plan.json")
        operations = document["request"]["operations"]
        checked = validate_operations(
            [
                {**op, "source_model_id": "a" * 32} if op["op"] == "assemble_component" else op
                for op in operations
            ]
        )
        self.assertEqual(len(checked), 3)
        labels = [op["label"] for op in checked]
        self.assertEqual(len(labels), len(set(labels)))
        self.assertEqual(checked[1]["source_model_id"], checked[0]["source_model_id"])

    def test_rebuild_pipeline_steps_use_real_tool_arguments(self):
        document = load("assembly_rebuild_pipeline.json")
        steps = document["steps"]
        self.assertEqual(
            [step["tool"] for step in steps],
            [
                "creo_inspect_session_assembly",
                "creo_adopt_file",
                "creo_adopt_file",
                "creo_new_assembly",
                "creo_execute_plan",
                "creo_get_job",
                "creo_list_components",
                "creo_execute_plan",
            ],
        )
        adopt_inspect = steps[1]["arguments"]
        adopt_apply = steps[2]["arguments"]
        self.assertEqual(adopt_inspect["mode"], "inspect")
        self.assertEqual(
            set(adopt_apply), {"file_path", "mode", "evidence_token", "idempotency_key"}
        )
        self.assertEqual(adopt_apply["file_path"], adopt_inspect["file_path"])
        self.assertEqual(steps[2]["arguments"]["evidence_token"], "<evidence_token from step 2>")
        for index in (4, 7):
            operations = steps[index]["arguments"]["operations"]
            validate_operations(
                [
                    {**op, "source_model_id": "a" * 32} if op["op"] == "assemble_component" else op
                    for op in operations
                ]
            )
        # Repeated occurrences reuse the adopted model_id with distinct labels.
        step5 = steps[4]["arguments"]["operations"]
        self.assertEqual(step5[1]["source_model_id"], step5[2]["source_model_id"])
        self.assertNotEqual(step5[1]["label"], step5[2]["label"])

    def test_pipeline_labels_and_no_raw_matrix_reuse(self):
        document = load("assembly_rebuild_pipeline.json")
        text = json.dumps(document, ensure_ascii=False)
        self.assertFalse(re.search(r'"transform_to_parent_raw"\s*:\s*\[\[', text))
        for step in document["steps"]:
            for op in step.get("arguments", {}).get("operations", []):
                if op["op"] == "assemble_component":
                    self.assertRegex(op["label"], r"^[a-z][a-z0-9_]{0,27}$")


if __name__ == "__main__":
    unittest.main()
