"""BUG-102: split the draft flip into request and effect, and keep -1 actionable.

The 0.10.0 feedback asked one draft on a face bounded by a chamfer and a round
(R3) with angle 10: 0.9.0 succeeded (+264.19 mm3) while 0.10.0 failed with a
bare ``ProFeatureWithoptionsCreate=-1``. The same report shows ``flip=false``
echoed back as ``draft_geometry.flip=true``, so the caller cannot tell whether
the value is what it asked for or what the feature tree ended up with.

This batch does not decide *why* the geometry failed (that needs the single
assigned session), so no test claims a fix. It locks what must be true either
way: the request is echoed unchanged, the effective value comes only from the
tree, and a failure carries the kernel's own element evidence instead of a bare
code.
"""

import unittest
from pathlib import Path

from creo_mechdog import operation_results

NATIVE = Path(__file__).resolve().parents[2] / "native"


def native_source(name: str) -> str:
    return (NATIVE / name).read_text(encoding="utf-8")


def draft_record(**overrides) -> dict:
    record = {
        "op": "draft",
        "index": 0,
        "label": "d11_wall",
        "succeeded": True,
        "draft_geometry": {
            "source": "feature_tree",
            "query_code": 0,
            "flip": True,
            "requested_flip": False,
            "effective_flip": True,
            "angle_deg": 5.0,
        },
    }
    record.update(overrides)
    return record


class NativeDraftContractTests(unittest.TestCase):
    def test_readback_separates_request_from_effective_value(self):
        source = native_source("advanced.cpp")
        for token in ("requested_flip", "effective_flip", "draft_geometry_json"):
            with self.subTest(token=token):
                self.assertIn(token, source)
        # The requested value must come from the operation, not the tree.
        self.assertIn('draft_geometry_json(f, op.value("flip", false))', source)

    def test_failure_carries_element_evidence_and_a_classification(self):
        source = native_source("advanced.cpp")
        start = source.index("static J generic_draft(")
        end = source.index("static void generic_sweep(", start)
        body = source[start:end]
        for token in (
            "draft_failure",
            "requested_flip",
            "element_errors",
            "no_element_evidence",
            "kernel_element_error",
            "ProElementFree(&root)",
        ):
            with self.subTest(token=token):
                self.assertIn(token, body)

    def test_failure_note_offers_a_next_action(self):
        source = native_source("advanced.cpp")
        start = source.index("static J generic_draft(")
        body = source[start : source.index("static void generic_sweep(", start)]
        self.assertIn("smaller angle", body)
        self.assertIn("creo_inspect_model", body)


class DraftProjectionTests(unittest.TestCase):
    def annotate(self, result: dict) -> dict:
        return operation_results.annotate_native_result(result, readonly=False, inputs=[])

    def test_projection_passes_both_flip_fields_through(self):
        result = self.annotate({"operations": [draft_record()]})
        geometry = result["operations"][0]["draft_geometry"]
        self.assertIs(geometry["requested_flip"], False)
        self.assertIs(geometry["effective_flip"], True)
        self.assertIs(geometry["flip"], True)

    def test_projection_never_fabricates_the_effective_value(self):
        record = draft_record()
        record["draft_geometry"] = {
            "source": "feature_tree",
            "query_code": 0,
            "flip": None,
            "requested_flip": True,
            "effective_flip": None,
            "angle_deg": 10.0,
        }
        result = self.annotate({"operations": [record]})
        geometry = result["operations"][0]["draft_geometry"]
        self.assertIsNone(geometry["effective_flip"])
        self.assertIs(geometry["requested_flip"], True)

    def test_failed_draft_keeps_the_failure_block(self):
        result = self.annotate(
            {
                "operations": [
                    {
                        "op": "draft",
                        "index": 0,
                        "label": "d11_wall",
                        "succeeded": False,
                        "draft_failure": {
                            "api": "ProFeatureWithoptionsCreate",
                            "requested_flip": False,
                            "angle_deg": 10.0,
                            "surface_count": 1,
                            "classification": "no_element_evidence",
                            "element_errors": {"total": 0, "truncated": False, "sample": []},
                            "note": "smaller angle",
                        },
                    }
                ]
            }
        )
        failure = result["operations"][0]["draft_failure"]
        self.assertEqual(failure["classification"], "no_element_evidence")
        self.assertEqual(failure["angle_deg"], 10.0)
