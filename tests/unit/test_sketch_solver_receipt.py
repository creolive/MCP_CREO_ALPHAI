"""DEV-071: a recoverable initial solve error is distinct from final failure."""

import unittest

import bridge
from creo_mechdog.failure_context import annotate_failed_operation
from creo_mechdog.operation_results import annotate_native_result


def receipt(completed=True):
    return {
        "requested": "auto",
        "used": "coordinates",
        "selection_reason": "entity_count",
        "stages": {
            "initial_solve": -1,
            "retry_without_inference": -1,
            "autodimension": 0,
            "section_regenerate": 0 if completed else None,
        },
        "completed": completed,
        "recovered": completed,
    }


class SketchSolverReceiptTests(unittest.TestCase):
    def test_success_keeps_recovery_codes_in_selectable_compact_block(self):
        result = {
            "success": True,
            "operations": [
                {"op": "sketch", "label": "s01", "succeeded": True, "solver": receipt()}
            ],
        }
        normalized = annotate_native_result(result, readonly=False)
        view = bridge.compact_job({"status": "succeeded", "result": normalized}, ["solver"])
        solver = view["result"]["operations"][0]["solver"]
        self.assertTrue(solver["completed"])
        self.assertEqual(solver["stages"]["initial_solve"], -1)
        self.assertEqual(solver["stages"]["section_regenerate"], 0)

    def test_failed_operation_keeps_partial_native_solver_and_original_proerror(self):
        result = {
            "success": False,
            "failed_operation": {
                "index": 0,
                "operation": "sketch",
                "feature_label": "s01",
                "pro_error": -1,
                "pro_error_source": "toolkit",
                "solver": receipt(False),
            },
        }
        annotate_failed_operation(result)
        self.assertEqual(result["failed_operation"]["solver"], receipt(False))
        self.assertEqual(result["failed_operation"]["pro_error"], -1)

    def test_operation_solver_projects_only_bounded_native_facts(self):
        raw = receipt()
        raw["coordinate_geometry"] = {"targets": [1] * 1000}
        result = {
            "success": True,
            "aliases": {"s01": {"solver": raw}},
            "operations": [{"op": "sketch", "label": "s01", "succeeded": True, "solver": raw}],
        }
        normalized = annotate_native_result(result, readonly=False)
        solver = normalized["operations"][0]["solver"]
        self.assertEqual(solver, receipt())
        self.assertNotIn("coordinate_geometry", solver)

    def test_historical_creation_never_borrows_a_later_edits_solver(self):
        edited = receipt()
        edited.update(requested="autodim", selection_reason="edit_coordinate_upgrade")
        result = {
            "success": True,
            "aliases": {"s01": {"solver": edited}},
            "operations": [
                {"op": "sketch", "label": "s01", "succeeded": True},
                {"op": "update_sketch_geometry", "sketch": "s01", "succeeded": True},
            ],
        }
        normalized = annotate_native_result(result, readonly=False)
        self.assertNotIn("solver", normalized["operations"][0])
        self.assertNotIn("solver", normalized["operations"][1])

    def test_missing_or_invalid_codes_never_become_success(self):
        raw = {
            "requested": "auto",
            "used": "autodim",
            "stages": {"initial_solve": True, "autodimension": "0"},
            "completed": "true",
        }
        result = {"success": False, "failed_operation": {"solver": raw}}
        annotate_failed_operation(result)
        solver = result["failed_operation"]["solver"]
        self.assertIsNone(solver["stages"]["initial_solve"])
        self.assertIsNone(solver["stages"]["autodimension"])
        self.assertIsNone(solver["completed"])
        legacy = {"success": False, "failed_operation_index": 0}
        annotate_failed_operation(legacy, [{"op": "sketch", "dimensioning": "auto"}])
        self.assertNotIn("solver", legacy["failed_operation"])

    def test_regeneration_feature_states_do_not_become_proerror_codes(self):
        result = {
            "success": False,
            "failed_operation_index": 1,
            "toolkit_code": -1,
            "failed_features": [{"id": 51, "name": "EX1", "type": 916, "status": 6}],
            "message": "Regeneration produced a failed feature",
        }
        annotate_failed_operation(result, [{"op": "sketch"}, {"op": "extrude", "label": "e03"}])
        block = result["failed_operation"]
        self.assertEqual(block["failed_features"]["sample"][0]["status"], 6)
        self.assertEqual(block["failed_features"]["total"], 1)
        self.assertIsNone(block["pro_error"])
        self.assertEqual(block["pro_error_source"], "unsupported")


if __name__ == "__main__":
    unittest.main()
