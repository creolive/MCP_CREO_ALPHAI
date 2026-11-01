import copy
import json
import re
import unittest

from tools.convert_p12_feedback import SOURCE, THICKNESS, convert_recipe
from tools.test_p12_blade import stage_batches


class P12ConversionTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tree = json.loads(SOURCE.read_text(encoding="utf-8"))
        cls.manifest = convert_recipe(cls.tree, route="strip_prism")

    def test_counts_batches_and_thickness(self):
        m = self.manifest
        self.assertEqual((m["source_feature_count"], m["split_only_operation_count"], m["operation_count"]), (391, 583, 580))
        self.assertEqual([len(b["operations"]) for b in m["batches"]], [194, 192, 192, 2])
        self.assertEqual(len(m["triangles"]), 96)
        self.assertEqual({op["depth"] for b in m["batches"] for op in b["operations"] if op["op"] == "extrude" and op.get("new_body")}, {THICKNESS})

    def test_repeated_point_names_are_group_scoped(self):
        ops = {op.get("label"): op for b in self.manifest["batches"] for op in b["operations"]}
        first = ops["pl00a"]["reference"]["points"]
        later = ops["pl01a"]["reference"]["points"]
        self.assertEqual(first, ["dp00a_a", "dp00a_b", "dp00a_c"])
        self.assertEqual(later, ["dp01a_a", "dp01a_b", "dp01a_c"])
        self.assertTrue(set(first).isdisjoint(later))
        self.assertTrue(all(re.fullmatch(r"[a-z][a-z0-9_]{0,27}", label) for label in ops))

    def test_stage_never_exceeds_plan_limit(self):
        self.assertEqual([len(x) for x in stage_batches(self.manifest, 1)], [14])
        self.assertEqual([len(x) for x in stage_batches(self.manifest, 4)], [50])
        self.assertEqual([len(x) for x in stage_batches(self.manifest, 48)], [194, 192, 192])

    def test_unmapped_fields_block(self):
        tree = copy.deepcopy(self.tree)
        tree["features"][0]["mystery"] = 1
        result = convert_recipe(tree, route="strip_prism")
        self.assertEqual(result["status"], "blocked")
        self.assertTrue(any(x.get("field") == "mystery" for x in result["unresolved"]))

    def test_invalid_source_rejected(self):
        with self.assertRaises(ValueError):
            convert_recipe({"features": []}, route="strip_prism")
        with self.assertRaises(ValueError):
            convert_recipe(self.tree, route="other")


if __name__ == "__main__":
    unittest.main()
