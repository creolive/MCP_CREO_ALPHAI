"""FEAT-035 increment: the hole receipt must say which depth basis it used.

From 0.10.0 a custom blind hole dimensions ``depth`` to the drill tip
(``PRO_HLE_DEP_TIP_DIM_SCHEME``). That口径 was only disclosed in release notes,
so a stored plan replayed against 0.9.0 silently becomes shallower and the
client has no field to check. The receipt therefore reports the scheme read
back from the created feature tree - never a default, never an inference from
the request.
"""

import unittest
from pathlib import Path

import bridge
from creo_mechdog import operation_results

ROOT = Path(__file__).resolve().parents[2]
NATIVE = ROOT / "native"


def native_source(name: str) -> str:
    return (NATIVE / name).read_text(encoding="utf-8")


def hole_record(**overrides) -> dict:
    record = {
        "op": "hole",
        "index": 0,
        "label": "h1",
        "succeeded": True,
        "feature_id": 12,
        "material_removed_mm3": 78.53981634,
        "depth_basis": "tip",
        "depth_scheme_code": 3,
        "depth_scheme_query": "PRO_E_HLE_DEPTH_DIM_TYPE",
    }
    record.update(overrides)
    return record


class NativeHoleContractTests(unittest.TestCase):
    def test_hole_reads_the_scheme_back_from_the_feature_tree(self):
        source = native_source("generic.cpp")
        start = source.index("static J hole_depth_basis_json(")
        body = source[start : source.index("static J generic_hole(", start)]
        for token in (
            "PRO_E_HLE_DEPTH_DIM_TYPE",
            "ProFeatureElemtreeExtract",
            "depth_basis",
            "depth_scheme_code",
            "PRO_HLE_DEP_TIP_DIM_SCHEME",
        ):
            with self.subTest(token=token):
                self.assertIn(token, body)

    def test_tip_is_only_claimed_for_the_tip_constant(self):
        source = native_source("generic.cpp")
        start = source.index("static J hole_depth_basis_json(")
        body = source[start : source.index("static J generic_hole(", start)]
        self.assertIn('value == PRO_HLE_DEP_TIP_DIM_SCHEME ? "tip" : "not_tip"', body)
        self.assertNotIn('"shoulder"', body)

    def test_unreadable_tree_leaves_the_basis_null(self):
        source = native_source("generic.cpp")
        start = source.index("static J hole_depth_basis_json(")
        body = source[start : source.index("static J generic_hole(", start)]
        self.assertIn('{"depth_basis", nullptr}', body)
        self.assertIn("if (code != PRO_TK_NO_ERROR)", body)


class HoleProjectionTests(unittest.TestCase):
    def annotate(self, result: dict) -> dict:
        return operation_results.annotate_native_result(result, readonly=False, inputs=[])

    def test_projection_passes_the_basis_fields_through(self):
        result = self.annotate({"operations": [hole_record()]})
        record = result["operations"][0]
        self.assertEqual(record["depth_basis"], "tip")
        self.assertEqual(record["depth_scheme_query"], "PRO_E_HLE_DEPTH_DIM_TYPE")
        self.assertEqual(record["depth_scheme_code"], 3)

    def test_projection_never_defaults_the_basis(self):
        record = hole_record()
        for key in ("depth_basis", "depth_scheme_code", "depth_scheme_query"):
            record.pop(key)
        result = self.annotate({"operations": [record]})
        self.assertNotIn("depth_basis", result["operations"][0])

    def test_compact_receipt_keeps_the_basis_fields(self):
        result = {"operations": [hole_record()]}
        compact = bridge.compact_job({"job_id": "j", "status": "succeeded", "result": result})
        record = compact["result"]["operations"][0]
        self.assertEqual(record["depth_basis"], "tip")
        self.assertEqual(record["depth_scheme_query"], "PRO_E_HLE_DEPTH_DIM_TYPE")
