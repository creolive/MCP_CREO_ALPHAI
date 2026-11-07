"""The native mismatch candidate list survives failed-result compaction."""

import unittest
from pathlib import Path

import bridge

ROOT = Path(__file__).resolve().parents[2]


class EdgeGeometryDiagnosticTest(unittest.TestCase):
    def test_native_stages_bounded_structured_candidates_before_failure(self):
        source = (ROOT / "native" / "advanced.cpp").read_text(encoding="utf-8")
        block = source[source.index("if (scan.matches.empty())") :]
        self.assertIn("geometry_diagnostics::nearest_candidates(scan.candidates)", block)
        self.assertIn('"nearest_edges", nearest_edges', block)
        self.assertIn('"endpoint_errors_mm"', block)
        self.assertLess(
            block.index('stage_operation_result({{"edge_geometry_diagnostic"'),
            block.index("throw std::runtime_error("),
        )

    def test_failed_compact_receipt_preserves_candidates(self):
        diagnostic = {
            "nearest_edges": [
                {
                    "id": 84,
                    "endpoints_mm": [[-92.5, -116, 1], [87.5, -116, 1]],
                    "endpoint_errors_mm": [0, 5],
                }
            ],
            "tolerance_mm": 0.01,
            "candidate_limit": 5,
            "straight_edge_count": 12,
        }
        operation = {
            "op": "sheetmetal_flange",
            "index": 0,
            "execution_status": "failed",
            "effect_status": "rolled_back",
            "succeeded": False,
            "edge_geometry_diagnostic": diagnostic,
        }
        job = {
            "job_id": "j",
            "status": "failed",
            "result": {"success": False, "failed_operation_index": 0, "operations": [operation]},
        }
        compact = bridge.compact_job(job)
        self.assertEqual(compact["result"]["operations"][0]["edge_geometry_diagnostic"], diagnostic)


if __name__ == "__main__":
    unittest.main()
