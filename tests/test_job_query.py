"""Polling contracts: bounded payloads must preserve outcome and recovery data."""

import copy
import json
import unittest
from unittest.mock import patch
import bridge


class JobQuery(unittest.TestCase):
    def test_compact_retains_final_evidence_and_drops_geometry(self):
        geometry = [{"id": i, "bbox": [[0, 0, 0], [1, 2, 3]]} for i in range(1000)]
        manifest = {
            "job_id": "a" * 32,
            "status": "succeeded",
            "model_id": "b" * 32,
            "revision": 7,
            "operations": [{"op": "sketch", "entities": geometry}],
            "result": {
                "success": True,
                "part_file": "owned.prt.8",
                "sha256": "proof",
                "saved_file_reloaded_and_verified": True,
                "inspection": {
                    "features": geometry,
                    "edges": geometry,
                    "surfaces": geometry,
                    "healthy": True,
                    "has_solid": True,
                    "units": "mm",
                    "volume_mm3": 123.5,
                },
                "aliases": {"profile": geometry},
                "operations": [{"op": "sketch", "succeeded": True, "inspection": geometry}],
            },
        }
        before = copy.deepcopy(manifest)
        compact = bridge.compact_job(manifest)
        self.assertEqual(manifest, before)
        self.assertEqual(compact["revision"], 7)
        self.assertEqual(compact["result"]["sha256"], "proof")
        self.assertTrue(compact["result"]["saved_file_reloaded_and_verified"])
        self.assertEqual(compact["result"]["inspection"]["volume_mm3"], 123.5)
        self.assertEqual(compact["result"]["inspection"]["counts"]["features"], 1000)
        self.assertLess(len(json.dumps(compact)), len(json.dumps(manifest)) // 20)

    def test_compact_preserves_failed_and_unknown_outcomes(self):
        for status in ("failed", "unknown_outcome"):
            result = bridge.compact_job(
                {
                    "job_id": "a" * 32,
                    "status": status,
                    "message": "inspect before retry",
                    "native_log_tail": "x" * 5000,
                    "result": {
                        "success": False,
                        "toolkit_code": -1,
                        "rollback_succeeded": False,
                        "rollback_code": -8,
                        "rollback_message": "recover saved baseline",
                    },
                }
            )
            self.assertEqual(result["status"], status)
            self.assertEqual(result["message"], "inspect before retry")
            self.assertFalse(result["result"]["rollback_succeeded"])
            self.assertEqual(result["result"]["rollback_code"], -8)
            self.assertNotIn("native_log_tail", result)

    def test_compact_running_keeps_stage_without_claiming_full_result(self):
        result = bridge.compact_job(
            {"job_id": "a" * 32, "status": "running", "stage": "sweep", "operations": [{}] * 4}
        )
        self.assertEqual(result["stage"], "sweep")
        self.assertEqual(result["operation_count"], 4)
        self.assertFalse(result["full_result_available"])

    def test_invalid_detail_rejected_even_without_jobs(self):
        with self.assertRaises(ValueError):
            bridge.get_job("a" * 32, detail="invalid")
        with self.assertRaises(ValueError):
            bridge.list_jobs(detail="invalid")


if __name__ == "__main__":
    unittest.main()
