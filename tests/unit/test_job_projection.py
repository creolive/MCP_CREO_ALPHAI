"""R04 (FEAT-023/FEAT-039): compact projection keeps the acceptance criteria.

Offline only; nothing connects to Creo. The contract frozen here:

- the measured surface-chain criteria (trim areas and kept-side basis, offset
  source area and measured distance, projection length/endpoints/route and the
  solidify closure) are visible in ``detail=compact``;
- ``null`` and ``reason`` are copied exactly and never become ``0``;
- compact drops raw log text while ``detail=full`` keeps it;
- 35 and 1000 operations stay inside the 32 KiB budget, and a failure outside
  the sample window keeps its evidence;
- ``sections`` selects blocks before the operation projection; an empty array
  still keeps only result evidence;
- a 50-item compact list stays inside 32768 B, each item at or below 640 B,
  with a bounded message and the ``job_id`` as the detail entry;
- ``full_detail_hint`` names detail/section/limit/cursor.
"""

from __future__ import annotations

import json
import shutil
import tempfile
import unittest
from pathlib import Path

import bridge
from creo_mechdog.job_projection import (
    FULL_DETAIL_HINT,
    LIST_ITEM_BUDGET,
    compact_job_list_item,
    compact_operation,
    compact_progress,
)
from creo_mechdog.model_queries import RESPONSE_BUDGET, serialized_size

JOB_ID = "a" * 32
LIST_BUDGET = 32768


def utf8_bytes(value) -> int:
    return len(json.dumps(value, ensure_ascii=False).encode("utf-8"))


def operation(op: str, index: int = 0, **extra) -> dict:
    record = {
        "op": op,
        "index": index,
        "label": f"{op}_{index:03d}",
        "succeeded": True,
        "execution_status": "succeeded",
        "effect_status": "committed",
        "message": "ok",
    }
    record.update(extra)
    return record


def manifest(operations: list[dict], *, status: str = "succeeded", **result_extra) -> dict:
    result = {
        "success": status == "succeeded",
        "message": "ok",
        "toolkit_code": 0,
        "saved_file_reloaded_and_verified": True,
        "sha256": "b" * 64,
        "part_file": "model.prt.1",
        "operations": operations,
    }
    result.update(result_extra)
    return {
        "job_id": JOB_ID,
        "kind": "native",
        "model_id": "c" * 32,
        "status": status,
        "stage": "verified",
        "revision": 7,
        "created_at": "2026-11-06T00:00:00+00:00",
        "finished_at": "2026-11-06T00:01:00+00:00",
        "message": "saved and verified",
        "result": result,
    }


def first_operation(summary: dict) -> dict:
    return summary["result"]["operations"][0]


class CriteriaVisibilityTests(unittest.TestCase):
    """The compact view carries what the native executor measured."""

    def test_surface_trim_keeps_area_status_and_kept_side_basis(self):
        trim = operation(
            "surface_trim",
            area_before_mm2=800.0,
            area_before_status={"available": True, "reason": None},
            area_after_mm2=None,
            area_after_status={"available": False, "reason": "kept_quilt_unresolved"},
            keep_side="one",
            offset_mm=None,
            offset_side=None,
            kept_quilt_id=12,
            kept_quilt_source="feature_visit",
            kept_quilt_visit_code=0,
            kept_side_basis={
                "keep_side": "one",
                "tool_kind": "quilt",
                "tool_normal": None,
                "target_centroid": None,
                "kept_centroid": None,
                "signed_offset_mm": None,
                "centroid_status": {
                    "available": False,
                    "reason": "quilt_centroid_not_measured",
                },
            },
            padding="x" * 4000,
        )
        record = first_operation(bridge.compact_job(manifest([trim])))
        self.assertEqual(record["area_before_mm2"], 800.0)
        self.assertEqual(record["area_before_status"]["available"], True)
        self.assertIsNone(record["area_after_mm2"])
        self.assertEqual(record["area_after_status"]["reason"], "kept_quilt_unresolved")
        self.assertEqual(record["kept_side_basis"]["tool_normal"], None)
        self.assertEqual(
            record["kept_side_basis"]["centroid_status"]["reason"],
            "quilt_centroid_not_measured",
        )
        self.assertEqual(record["kept_quilt_id"], 12)
        self.assertNotIn("padding", record)

    def test_surface_offset_keeps_source_area_and_measured_distance(self):
        offset = operation(
            "surface_offset",
            target_quilt_id=12,
            source_area_mm2=None,
            source_area_status={
                "available": False,
                "init_code": -1,
                "query_code": None,
                "reason": "quilt_init_failed",
            },
            offset_distance_mm=5.0,
            measured_offset_distance_mm=None,
            direction="positive",
            offset_method="normal_to_surface",
            volume_before_mm3=4000.0,
            volume_after_mm3=8000.0,
        )
        record = first_operation(bridge.compact_job(manifest([offset])))
        self.assertIsNone(record["source_area_mm2"])
        self.assertEqual(record["source_area_status"]["init_code"], -1)
        self.assertEqual(record["source_area_status"]["reason"], "quilt_init_failed")
        self.assertIsNone(record["measured_offset_distance_mm"])
        self.assertEqual(record["offset_distance_mm"], 5.0)
        self.assertEqual(record["direction"], "positive")
        self.assertEqual(record["offset_method"], "normal_to_surface")
        self.assertEqual(record["target_quilt_id"], 12)

    def test_project_curve_keeps_length_endpoints_curve_helper_and_route(self):
        projection = operation(
            "project_curve",
            source_curve_id=7,
            source_length_mm=30.0,
            source_length_status={"available": True, "reason": None},
            target_quilt_id=12,
            side="positive",
            direction=[0.0, 0.0, 1.0],
            direction_basis="datum_plane_normal",
            direction_length=1.0,
            target_bounds_known=True,
            target_bounds_code=0,
            route="swept_surface_intersect",
            helper_feature_id=120,
            helper_sweep_depth_mm=42.0,
            curve_feature_id=121,
            curve_id=122,
            curve_length_mm=42.5,
            curve_length_status={"available": True, "reason": None},
            endpoints_mm=[[0.0, 0.0, 0.0], [0.0, 40.0, 0.0]],
            endpoints_status={"available": True, "reason": None},
        )
        record = first_operation(bridge.compact_job(manifest([projection])))
        self.assertEqual(record["curve_length_mm"], 42.5)
        self.assertEqual(record["endpoints_mm"], [[0.0, 0.0, 0.0], [0.0, 40.0, 0.0]])
        self.assertEqual(record["curve_id"], 122)
        self.assertEqual(record["helper_feature_id"], 120)
        self.assertEqual(record["route"], "swept_surface_intersect")
        self.assertEqual(record["source_length_mm"], 30.0)

    def test_solidify_keeps_the_measured_closure_with_its_null_reason(self):
        solid = operation(
            "solidify",
            target_quilt_id=12,
            closure={"available": False, "query_code": -4, "reason": None},
            side="positive",
            volume_before_mm3=None,
            volume_after_mm3=None,
        )
        record = first_operation(bridge.compact_job(manifest([solid])))
        self.assertEqual(record["closure"], {"available": False, "query_code": -4, "reason": None})
        self.assertIsNone(record["volume_before_mm3"])
        self.assertEqual(record["target_quilt_id"], 12)

    def test_missing_measurements_stay_absent_not_zero(self):
        record = compact_operation(operation("surface_trim", area_before_mm2=None))
        self.assertIsNone(record["area_before_mm2"])
        self.assertNotIn("area_after_mm2", record)
        self.assertNotIn("closure", record)


class LogRemovalTests(unittest.TestCase):
    def setUp(self):
        self.root = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, self.root, ignore_errors=True)
        jobs = bridge.JOBS
        bridge.JOBS = self.root
        self.addCleanup(setattr, bridge, "JOBS", jobs)

    def test_compact_drops_top_level_and_nested_log_text(self):
        data = manifest([operation("sketch")], status="failed")
        data["native_log_tail"] = "PHASE=verify_model\n" + "x" * 5000
        data["native_progress"] = {
            "readable": True,
            "stage": "verify_model",
            "sub_stage": "verify_model_save",
            "elapsed_ms": 41,
            "idle_seconds": 3.5,
            "log_tail": "SECRET native log",
        }
        compact = bridge.compact_job(data)
        self.assertNotIn("native_log_tail", compact)
        self.assertNotIn("log_tail", json.dumps(compact))
        self.assertEqual(compact["native_progress"]["stage"], "verify_model")
        self.assertEqual(compact["native_progress"]["elapsed_ms"], 41)
        self.assertEqual(compact["native_progress"]["idle_seconds"], 3.5)

    def test_full_detail_keeps_the_native_log_tail(self):
        job_id = "d" * 32
        directory = self.root / job_id
        directory.mkdir()
        data = manifest([operation("sketch")], status="failed")
        bridge.write_json(directory / "job.json", data)
        (directory / "native.log").write_text("y" * 5000 + "\nPHASE=verify_model", encoding="utf-8")
        full = bridge.get_job(job_id, detail="full")
        self.assertIn("PHASE=verify_model", full["native_log_tail"])
        compact = bridge.get_job(job_id, detail="compact")
        self.assertNotIn("native_log_tail", compact)

    def test_progress_projection_keeps_only_stage_and_timings(self):
        projected = compact_progress(
            {"stage": "sweep", "idle_seconds": 1.5, "log_tail": "raw", "extra": [1, 2]}
        )
        self.assertEqual(projected, {"stage": "sweep", "idle_seconds": 1.5})

    def test_full_detail_hint_names_the_pagination_parameters(self):
        compact = bridge.compact_job(manifest([operation("sketch")]))
        hint = compact["full_detail_hint"]
        self.assertEqual(hint, FULL_DETAIL_HINT)
        for token in ("detail", "section", "limit", "cursor", "operations_result"):
            with self.subTest(token=token):
                self.assertIn(token, hint)


class BudgetAndSamplingTests(unittest.TestCase):
    def ops(self, count: int, *, failed_at: int | None = None) -> list[dict]:
        records = [operation("sketch" if i % 2 == 0 else "extrude", i) for i in range(count)]
        if failed_at is not None:
            records[failed_at].update(
                succeeded=False,
                execution_status="failed",
                effect_status="rolled_back",
                message=f"CompleteFeature failed at {failed_at}",
                feature_errors={
                    "api": "ProFeatureWithoptionsCreate",
                    "code": -1,
                    "failed_stage": "CompleteFeature",
                    "element_errors": {"total": 1, "truncated": False, "sample": []},
                    "section_errors": {
                        "available": True,
                        "total": 1,
                        "truncated": False,
                        "sample": ["seg_1"],
                    },
                },
                failed_operation={
                    "index": failed_at,
                    "operation": "extrude",
                    "stage": "CompleteFeature",
                },
            )
        return records

    def test_thirty_five_operations_fit_with_every_record(self):
        compact = bridge.compact_job(manifest(self.ops(35)))
        result = compact["result"]
        self.assertLessEqual(utf8_bytes(compact), RESPONSE_BUDGET)
        self.assertEqual(result["operations_total"], 35)
        self.assertFalse(result["operations_truncated"])
        self.assertEqual(len(result["operations"]), 35)

    def test_one_thousand_operations_are_sampled_inside_the_budget(self):
        compact = bridge.compact_job(manifest(self.ops(1000)))
        result = compact["result"]
        self.assertLessEqual(utf8_bytes(compact), RESPONSE_BUDGET)
        self.assertLessEqual(serialized_size(compact), RESPONSE_BUDGET)
        self.assertEqual(result["operations_total"], 1000)
        self.assertTrue(result["operations_truncated"])
        self.assertLessEqual(len(result["operations"]), 21)

    def test_a_failure_outside_the_sample_keeps_its_evidence(self):
        compact = bridge.compact_job(manifest(self.ops(1000, failed_at=998), status="failed"))
        kept = compact["result"]["operations"]
        self.assertLessEqual(serialized_size(compact), RESPONSE_BUDGET)
        failed = [record for record in kept if record.get("index") == 998]
        self.assertEqual(len(failed), 1)
        record = failed[0]
        self.assertEqual(record["execution_status"], "failed")
        self.assertEqual(record["message"], "CompleteFeature failed at 998")
        self.assertEqual(record["feature_errors"]["failed_stage"], "CompleteFeature")
        self.assertEqual(record["failed_operation"]["stage"], "CompleteFeature")

    def test_sections_select_blocks_before_the_operation_projection(self):
        trim = operation(
            "surface_trim",
            area_before_mm2=800.0,
            area_after_mm2=600.0,
            kept_side_basis={"keep_side": "one"},
        )
        data = manifest([trim])
        full_blocks = bridge.compact_job(data, sections=["operations"])
        self.assertEqual(first_operation(full_blocks)["area_before_mm2"], 800.0)
        selected = bridge.compact_job(data, sections=["extrude_depth"])
        record = first_operation(selected)
        self.assertEqual(record["index"], 0)
        self.assertNotIn("area_before_mm2", record)
        empty = bridge.compact_job(data, sections=[])
        self.assertNotIn("operations", empty["result"])
        self.assertEqual(empty["sections_applied"], [])


class ListItemTests(unittest.TestCase):
    def test_item_keeps_identity_state_and_message_only(self):
        item = compact_job_list_item(
            {
                "job_id": JOB_ID,
                "model_id": "c" * 32,
                "status": "failed",
                "stage": "execute_extrude",
                "created_at": "2026-11-06T00:00:00+00:00",
                "finished_at": "2026-11-06T00:01:00+00:00",
                "revision": 8,
                "message": "failed",
                "result": {"success": False, "operations": [{"op": "extrude"}]},
            }
        )
        self.assertEqual(
            set(item),
            {
                "job_id",
                "model_id",
                "status",
                "stage",
                "created_at",
                "finished_at",
                "outcome",
                "message",
            },
        )
        self.assertEqual(item["outcome"], "failure")
        self.assertNotIn("revision", item)
        self.assertNotIn("result", item)
        self.assertLessEqual(serialized_size(item), LIST_ITEM_BUDGET)

    def test_outcome_classification_follows_status(self):
        for status, expected in (
            ("succeeded", "success"),
            ("failed", "failure"),
            ("unknown_outcome", "unknown"),
            ("running", "pending"),
        ):
            with self.subTest(status=status):
                item = compact_job_list_item({"job_id": JOB_ID, "status": status})
                self.assertEqual(item["outcome"], expected)

    def test_a_long_chinese_error_is_bounded_but_the_failed_operation_is_complete(self):
        text = "特征重建失败：" + "曲面偏置测得距离为零；" * 40
        failed_operation = {
            "index": 3,
            "operation": "surface_offset",
            "stage": "CompleteFeature",
            "message": text,
            "message_truncated": False,
            "pro_error": -1,
            "pro_error_source": "toolkit",
        }
        data = manifest(
            [operation("surface_offset", 3)],
            status="failed",
            message=text,
            failed_operation=failed_operation,
        )
        data["message"] = text
        compact = bridge.compact_job(data)
        self.assertEqual(compact["result"]["failed_operation"]["message"], text)
        self.assertEqual(compact["result"]["failed_operation"]["pro_error"], -1)
        item = compact_job_list_item(data)
        self.assertLessEqual(len(item["message"]), 200)
        self.assertLessEqual(serialized_size(item), LIST_ITEM_BUDGET)
        self.assertTrue(item["message_truncated"])
        self.assertTrue(text.startswith(item["message"].rstrip("…")))


class ListBudgetTests(unittest.TestCase):
    def setUp(self):
        self.root = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, self.root, ignore_errors=True)
        jobs = bridge.JOBS
        bridge.JOBS = self.root
        self.addCleanup(setattr, bridge, "JOBS", jobs)
        long_message = "长错误：" + "截面求解失败，" * 60
        for index in range(50):
            job_id = f"{index:032x}"
            data = manifest([operation("sketch")], status="failed", message=long_message)
            data["message"] = long_message
            data["job_id"] = job_id
            directory = self.root / job_id
            directory.mkdir()
            bridge.write_json(directory / "job.json", data)

    def test_fifty_compact_items_fit_the_list_budget(self):
        items = bridge.list_jobs(limit=50, detail="compact")
        self.assertEqual(len(items), 50)
        for item in items:
            with self.subTest(job_id=item["job_id"]):
                self.assertLessEqual(serialized_size(item), LIST_ITEM_BUDGET)
                self.assertLessEqual(serialized_size(item), 640)
                self.assertLessEqual(len(item["message"]), 200)
                self.assertNotIn("result", item)
        self.assertLessEqual(serialized_size(items), LIST_BUDGET)
        self.assertLessEqual(utf8_bytes(items), LIST_BUDGET)

    def test_list_detail_full_still_returns_the_per_job_view(self):
        items = bridge.list_jobs(limit=1, detail="full")
        self.assertEqual(items[0]["detail"], "full")
        self.assertIn("result", items[0])


if __name__ == "__main__":
    unittest.main()
