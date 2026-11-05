"""S08: the result shape of a surface chain stays auditable.

The chain cases add measurement fields (area, volume, closure) to the shared
operation result. These tests pin the four properties the plan names: the
compact projection keeps the status fields, a large candidate list stays
bounded, a failed chain keeps its effect status, and an old job never gains
measurements it never had.
"""

import unittest

from creo_mechdog import operation_results


def chain_result(**operation) -> dict:
    record = {
        "op": "surface_trim",
        "index": 0,
        "label": "chain_trim",
        "execution_status": "succeeded",
        "effect_status": "committed",
    }
    record.update(operation)
    return {
        "success": True,
        "operations": [record],
        "summary": {"operations": [dict(record)]},
    }


class SurfaceChainResultTests(unittest.TestCase):
    def test_compact_keeps_surface_measurement_status(self):
        self.assertIn("execution_status", operation_results.PROTECTED_OPERATION_KEYS)
        self.assertIn("effect_status", operation_results.PROTECTED_OPERATION_KEYS)
        summary = {
            "operations": [
                {
                    "op": "surface_trim",
                    "index": 0,
                    "execution_status": "failed",
                    "effect_status": "rolled_back",
                    "area_after_status": {"available": False, "reason": "not_measured"},
                    "area_after_mm2": 600.0,
                    "padding": "x" * 4000,
                }
            ]
        }
        bounded = operation_results.enforce_compact_budget(summary, budget=200)
        record = bounded["operations"][0]
        self.assertEqual(record["execution_status"], "failed")
        self.assertEqual(record["effect_status"], "rolled_back")
        self.assertIn("area_after_status", record)

    def test_large_quilt_candidates_stay_bounded(self):
        candidates = [{"quilt_id": index} for index in range(200)]
        bounded = operation_results.bounded_entries(candidates, limit=20)
        self.assertEqual(bounded.get("total"), 200)
        self.assertTrue(bounded.get("truncated"))
        self.assertLessEqual(len(bounded.get("sample") or []), 20)

    def test_failed_chain_preserves_effect_status(self):
        result = chain_result(
            execution_status="failed",
            effect_status="rolled_back",
            area_after_status={"available": False, "reason": "regeneration_failed"},
        )
        annotated = operation_results.annotate_native_result(result, readonly=False, inputs=[])
        record = annotated["operations"][0]
        self.assertEqual(record["execution_status"], "failed")
        self.assertEqual(record["effect_status"], "rolled_back")
        self.assertEqual(record["area_after_status"]["reason"], "regeneration_failed")

    def test_old_jobs_do_not_gain_fabricated_measurements(self):
        result = {
            "success": True,
            "operations": [
                {
                    "op": "sketch",
                    "index": 0,
                    "execution_status": "succeeded",
                    "effect_status": "committed",
                }
            ],
        }
        annotated = operation_results.annotate_native_result(result, readonly=False, inputs=[])
        record = annotated["operations"][0]
        for fabricated in ("area_after_mm2", "area_before_mm2", "volume_after_mm3", "closure"):
            self.assertNotIn(fabricated, record)


if __name__ == "__main__":
    unittest.main()
