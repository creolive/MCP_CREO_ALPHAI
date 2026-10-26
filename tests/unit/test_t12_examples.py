"""DEV-047 T12 official examples stay callable against the real MCP schema."""

import json
import math
import unittest

from creo_mechdog.paths import SOURCE_PATHS
from creo_mechdog.schema import validate_operations


def load(name):
    return json.loads((SOURCE_PATHS.resource_root / "examples" / name).read_text(encoding="utf-8"))


def materialize(document):
    operations = json.loads(json.dumps(document["request"]["operations"]))
    for operation in operations:
        if operation.get("op") == "draft":
            for surface in operation["surfaces"]:
                if surface.get("kind") == "surface" and not isinstance(surface.get("id"), int):
                    surface["id"] = 12345
    return operations


class BatchAppendExample(unittest.TestCase):
    def test_validates_against_real_schema(self):
        document = load("dev047_t12_batch_append.json")
        checked = validate_operations(materialize(document))
        self.assertEqual(len(checked), 6)
        labels = [op["label"] for op in checked]
        self.assertEqual(len(labels), len(set(labels)))

    def test_documents_transaction_and_limit_rules(self):
        document = load("dev047_t12_batch_append.json")
        text = json.dumps(document, ensure_ascii=False)
        for phrase in (
            "expected_revision",
            "saved_file_reloaded_and_verified",
            "rolls back",
            "200 operations",
            "revision",
        ):
            self.assertIn(phrase, text)

    def test_geometry_is_analytically_checkable(self):
        document = load("dev047_t12_batch_append.json")
        self.assertIn("16000 + 2000 + 500 - 90*pi", json.dumps(document))
        self.assertAlmostEqual(
            16000.0 + 2000.0 + 500.0 - 90.0 * math.pi, 18217.256661176918, places=6
        )


class DraftBossExample(unittest.TestCase):
    def test_validates_against_real_schema(self):
        document = load("dev047_t12_draft_boss.json")
        checked = validate_operations(materialize(document))
        self.assertEqual(len(checked), 3)
        draft = checked[2]
        self.assertEqual(draft["op"], "draft")
        self.assertEqual(draft["angle"], 11)
        self.assertEqual(draft["surfaces"][0]["kind"], "surface")
        self.assertIsInstance(draft["surfaces"][0]["id"], int)

    def test_face_reference_comes_from_inspection_not_hardcoding(self):
        document = load("dev047_t12_draft_boss.json")
        text = json.dumps(document, ensure_ascii=False)
        self.assertIn("creo_inspect_model", text)
        self.assertIn("geometry id", text)
        # The shipped file keeps a documented placeholder, never a real id.
        surfaces = document["request"]["operations"][2]["surfaces"]
        self.assertIsInstance(surfaces[0]["id"], str)

    def test_formula_constants_are_self_consistent(self):
        r_top = 3.0 - 3.0 * math.tan(math.radians(11.0))
        frustum = math.pi * 3.0 / 3.0 * (9.0 + 3.0 * r_top + r_top**2)
        cylinder = math.pi * 9.0 * 3.0
        self.assertAlmostEqual(r_top, 2.416859072586845, places=9)
        self.assertAlmostEqual(frustum, 69.40338944342489, places=6)
        self.assertAlmostEqual(cylinder - frustum, 15.419612203499526, places=6)
        self.assertAlmostEqual(frustum + math.pi * (18.0 - 3.0 * r_top - r_top**2), cylinder)


if __name__ == "__main__":
    unittest.main()
