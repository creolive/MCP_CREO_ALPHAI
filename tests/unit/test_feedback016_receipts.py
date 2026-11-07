"""DEV-071: persisted aliases reach public job views without inventing evidence."""

import copy
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import bridge
from creo_mechdog import model_registry, operation_results
from creo_mechdog.references import reference_capabilities

MITER = {
    "requested": True,
    "add": 1,
    "width_mm": 1.0,
    "offset_mm": 1.0,
    "width_type": -4,
    "offset_type": -4,
}
ADJACENCY = {"allowed_by_miter_cut": True, "edge_id": 266, "ends": []}


def result_fixture():
    return {
        "success": True,
        "aliases": {
            "wall": {
                "miter_cuts": copy.deepcopy(MITER),
                "adjacent_bend_ends_allowed": copy.deepcopy(ADJACENCY),
            }
        },
        "operations": [
            {
                "op": "sheetmetal_flange",
                "label": "wall",
                "index": 0,
                "succeeded": True,
                "execution_status": "succeeded",
            }
        ],
    }


class FeedbackReceiptsTests(unittest.TestCase):
    def test_closeout_copies_actual_flange_receipts(self):
        result = operation_results.annotate_native_result(result_fixture(), readonly=False)
        self.assertEqual(result["operations"][0]["miter_cuts"], MITER)
        self.assertEqual(result["operations"][0]["adjacent_bend_ends_allowed"], ADJACENCY)

    def test_unexecuted_failed_or_wrong_kind_never_borrows_an_alias(self):
        for extra in (
            {"execution_status": "not_executed", "succeeded": False},
            {"execution_status": "failed", "succeeded": False},
            {"op": "round"},
            {"op": ["sheetmetal_flange"]},
            {"label": "different"},
        ):
            with self.subTest(extra=extra):
                result = result_fixture()
                result["operations"][0].update(extra)
                projected = operation_results.annotate_native_result(result, readonly=False)
                self.assertNotIn("miter_cuts", projected["operations"][0])

    def test_existing_operation_receipt_is_authoritative_and_missing_stays_missing(self):
        result = result_fixture()
        result["operations"][0]["miter_cuts"] = {"requested": False}
        projected = operation_results.annotate_native_result(result, readonly=False)
        self.assertEqual(projected["operations"][0]["miter_cuts"], {"requested": False})
        result = result_fixture()
        result.pop("aliases")
        projected = operation_results.annotate_native_result(result, readonly=False)
        self.assertNotIn("miter_cuts", projected["operations"][0])

    def test_legacy_split_job_exposes_receipts_in_full_compact_and_sections(self):
        with tempfile.TemporaryDirectory() as raw:
            root = Path(raw)
            job_id = "a" * 32
            directory = root / "jobs" / job_id
            directory.mkdir(parents=True)
            with patch.object(bridge, "ROOT", root), patch.object(bridge, "JOBS", root / "jobs"):
                result = model_registry.split_job_result(result_fixture(), directory)
                manifest = {
                    "job_id": job_id,
                    "kind": "generic",
                    "status": "succeeded",
                    "stage": "verified",
                    "revision": 1,
                    "operations": [{"op": "sheetmetal_flange", "label": "wall"}],
                    "result": result,
                }
                bridge.write_json(directory / "job.json", manifest)
                original = (directory / "job.json").read_bytes()
                for detail in ("compact", "full"):
                    view = bridge.get_job(job_id, detail=detail)
                    op = view["result"]["operations"][0]
                    self.assertEqual(op["miter_cuts"], MITER)
                    self.assertEqual(op["adjacent_bend_ends_allowed"], ADJACENCY)
                selected = bridge.get_job(job_id, detail="compact", sections=["miter_cuts"])
                self.assertEqual(selected["result"]["operations"][0]["miter_cuts"], MITER)
                self.assertNotIn("adjacent_bend_ends_allowed", selected["result"]["operations"][0])
                page = bridge.get_job(job_id, detail="full", section="operations_result")
                self.assertEqual(page["data"]["operations_result"][0]["miter_cuts"], MITER)
                self.assertEqual((directory / "job.json").read_bytes(), original)

    def test_offset_contract_identifies_solid_volume_and_source_quilt(self):
        contract = reference_capabilities()["by_tool"]["creo_surface_offset"]
        self.assertIn("solid volume", contract["result"])
        self.assertIn("source quilt", contract["result"])
        self.assertNotIn("moves the quilt", contract["result"])


if __name__ == "__main__":
    unittest.main()
