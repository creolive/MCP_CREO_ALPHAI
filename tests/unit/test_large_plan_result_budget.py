"""FEAT-008/BUG-088 (Q13): compact budget and full pagination for large results.

Offline coverage only; nothing connects to Creo. The fixtures replay the F
feedback shapes (40+ operations, an 81-point contour, an 80-component recolor
receipt and multi-error results) and lock the measured contract:

- compact stays inside the 32 KiB response budget measured in real UTF-8
  bytes (not characters) and keeps the total/truncated markers;
- the new operation diagnostics (geometry_deviation, failed_model_cleanup,
  feature_errors, color/surface receipts) ride one bounded summary whose
  sample cap is 20, matching the existing diagnostics contract;
- failure reasons, revision, rollback and save/reload evidence are never cut;
- detail=full pages through the project's standard cursor, so the request
  input echo is never returned unbounded and missing pages stay retrievable.
"""

from __future__ import annotations

import copy
import json
import math
import unittest

import bridge
from creo_mechdog.job_pages import (
    ENTRY_BUDGET,
    SECTIONS,
    job_page,
    section_records,
)
from creo_mechdog.model_queries import (
    RESPONSE_BUDGET,
    decode_cursor,
)
from creo_mechdog.operation_results import (
    SAMPLE_LIMIT,
    bounded_summary,
    enforce_compact_budget,
)


def utf8_bytes(value) -> int:
    return len(json.dumps(value, ensure_ascii=False).encode("utf-8"))


def ascii_size(value) -> int:
    return len(json.dumps(value, ensure_ascii=True, indent=2).encode("utf-8"))


# ---------------------------------------------------------------------------
# Fixtures built from the F feedback shapes (40+ ops / 81 points / 80
# components / multi-error). Same shapes as the 2026-11-01 measurement.
# ---------------------------------------------------------------------------


def polyline_entities(n_points: int) -> list[dict]:
    points = []
    for i in range(n_points):
        angle = 2 * math.pi * i / (n_points - 1)
        points.append([round(50.0 * math.cos(angle), 6), round(30.0 * math.sin(angle), 6)])
    return [{"type": "polyline", "name": "blade_outline", "points": points, "closed": False}]


def sketch_op_record(index: int) -> dict:
    return {
        "op": "sketch",
        "index": index,
        "label": f"sk_{index:03d}",
        "succeeded": True,
        "execution_status": "succeeded",
        "effect_status": "committed",
        "native_section": {
            "available": True,
            "closed_contours": 1,
            "contours": 1,
            "entities": 4,
            "open_ends": 0,
        },
        "profile": {
            "source": "input",
            "analysis": "closed",
            "arc_geometry": [],
            "entity_count": 4,
            "contour_count": 1,
            "closed_contour_count": 1,
            "open_contour_count": 0,
            "material_area_mm2": 1234.5,
            "categories": {"near_tolerance": 0},
            "closure_tolerance_mm": 0.001,
            "max_endpoint_gap_mm": 0.0,
            "near_tolerance_pairs": {"total": 0, "truncated": False, "sample": []},
        },
    }


def polyline_op_record(index: int) -> dict:
    record = sketch_op_record(index)
    record["profile"]["entity_count"] = 81
    record["profile"]["analysis"] = "open"
    record["profile"]["open_contour_count"] = 1
    record["profile"]["closed_contour_count"] = 0
    record["profile"]["near_tolerance_pairs"] = {
        "total": 81,
        "truncated": True,
        "sample": [{"entities": [f"p{i}", f"p{i + 1}"], "gap_mm": 0.0009} for i in range(20)],
    }
    return record


def extrude_op_record(index: int) -> dict:
    return {
        "op": "extrude",
        "index": index,
        "label": f"ex_{index:03d}",
        "succeeded": True,
        "execution_status": "succeeded",
        "effect_status": "committed",
        "feature_id": 100 + index,
        "volume_before_mm3": 1000.0,
        "volume_after_mm3": 6000.0,
        "material_delta_mm3": 5000.0,
        "parameters": {"depth": 25.0, "direction": "positive"},
    }


def feature_errors_block(total: int = 37) -> dict:
    return {
        "api": "ProFeatureWithoptionsCreate",
        "code": -1,
        "failed_stage": "CompleteFeature",
        "element_errors": {
            "total": total,
            "truncated": total > SAMPLE_LIMIT,
            "sample": [{"element": 1000 + j, "type": 6002, "error": -1} for j in range(total)],
        },
        "section_errors": {
            "total": 12,
            "truncated": True,
            "sample": ["section entity seg_1 failed to regenerate"] * 12,
        },
    }


def build_result(n_ops: int, *, polyline: bool = True, failed: bool = False) -> dict:
    ops = []
    for i in range(n_ops):
        if i % 2 == 0:
            ops.append(polyline_op_record(i) if (polyline and i == 0) else sketch_op_record(i))
        else:
            ops.append(extrude_op_record(i))
    result = {
        "success": not failed,
        "toolkit_code": -1 if failed else 0,
        "message": (
            "failed at execute_extrude: ProFeatureWithoptionsCreate returned -1; "
            "element tree rejected the depth element"
            if failed
            else "ok"
        ),
        "part_file": r"E:\Projects\MCP_CREO_MechDog\jobs\aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa\output\model.prt.1",
        "sha256": "a" * 64,
        "saved_file_reloaded_and_verified": True,
        "rollback_succeeded": False if failed else None,
        "model_unchanged": True if failed else None,
        "rollback_message": "rollback confirmed; model unchanged" if failed else None,
        "rollback_code": 0 if failed else None,
        "preview_status": "written",
        "preview_code": 0,
        "preview_file": r"E:\jobs\aa\output\preview.jpg",
        "connected": True,
        "volume_mm3": 60318.578948924034,
        "failed_stage": "execute_extrude" if failed else None,
        "failed_toolkit_call": "ProFeatureWithoptionsCreate" if failed else None,
        "failed_operation_index": 3 if failed else None,
        "inspection_source": "saved_reloaded",
        "operations": ops,
    }
    if failed:
        marked = None
        for i in (3, 5, 7):
            if i >= len(ops):
                break
            ops[i]["succeeded"] = False
            ops[i]["execution_status"] = "failed"
            ops[i]["effect_status"] = "rolled_back"
            ops[i]["message"] = (
                "CompleteFeature failed: regeneration error on section entity "
                f"'seg_{i}'; ProFeatureWithoptionsCreate returned -1"
            )
            ops[i]["feature_errors"] = feature_errors_block()
            marked = ops[i]
        if marked is not None:
            result["feature_errors"] = copy.deepcopy(marked["feature_errors"])
    return result


def build_recolor_result(n_components: int = 80) -> dict:
    readback = [
        {
            "label": f"plate_{i:03d}",
            "family": f"family_{i % 12:02d}",
            "rgb_requested": [0.1 * (i % 10), 0.2, 0.3],
            "rgb_read": [0.1 * (i % 10), 0.2, 0.3],
            "abs_err": 0.001,
            "query_code": 0,
        }
        for i in range(n_components)
    ]
    baseline = [
        {
            "label": f"plate_{i:03d}",
            "appearance": {"state": "present", "rgb": [0.5, 0.5, 0.5], "query_code": 0},
        }
        for i in range(n_components)
    ]
    result = build_result(2, polyline=False)
    result["recolor"] = {
        "painted": n_components,
        "unmatched": [],
        "family_counts": {f"family_{i:02d}": 7 for i in range(12)},
        "readback_before_save": copy.deepcopy(readback),
        "readback_after_reload": copy.deepcopy(readback),
        "readback_tolerance": 0.01,
        "readback_all_within_tolerance": True,
        "component_appearance_baseline": baseline,
        "rollback_appearance_verified": True,
        "rollback_appearance_check": [
            {"label": f"plate_{i:03d}", "restored": True} for i in range(8)
        ],
    }
    result["component_changes"] = {
        "status": "committed",
        "changes": [
            {"op": "added", "label": f"plate_{i:03d}", "feature_id": 200 + i}
            for i in range(n_components)
        ],
    }
    return result


def build_manifest(result: dict, n_inputs: int, *, polyline: bool = True) -> dict:
    inputs = []
    for i in range(n_inputs):
        if i % 2 == 0:
            op = {
                "op": "sketch",
                "label": f"sk_{i:03d}",
                "plane": "XY",
                "dimensioning": "coordinates",
                "entities": polyline_entities(81)
                if (polyline and i == 0)
                else [
                    {
                        "type": "rectangle",
                        "name": "r",
                        "min": [-20, -10],
                        "max": [20, 10],
                    }
                ],
            }
        else:
            op = {
                "op": "extrude",
                "label": f"ex_{i:03d}",
                "sketch": f"sk_{i - 1:03d}",
                "depth": 25.0,
            }
        inputs.append(op)
    return {
        "job_id": "b" * 32,
        "kind": "generic",
        "model_id": "c" * 32,
        "status": "succeeded" if result.get("success") else "failed",
        "revision": 7,
        "readonly": False,
        "created_at": "2026-11-01T00:00:00+00:00",
        "started_at": "2026-11-01T00:00:01+00:00",
        "finished_at": "2026-11-01T00:01:00+00:00",
        "message": result.get("message"),
        "operations": inputs,
        "operation_count": n_inputs,
        "result": result,
    }


class CompactBudgetTests(unittest.TestCase):
    """compact projections stay inside the 32 KiB response budget."""

    def assert_within_budget(self, summary: dict) -> None:
        self.assertLessEqual(utf8_bytes(summary), RESPONSE_BUDGET)
        self.assertLessEqual(ascii_size(summary), RESPONSE_BUDGET)

    def test_forty_ops_with_an_eighty_one_point_contour_fit(self):
        manifest = build_manifest(build_result(42), 42)
        self.assert_within_budget(bridge.compact_job(copy.deepcopy(manifest)))

    def test_two_hundred_ops_fit(self):
        manifest = build_manifest(build_result(200), 200, polyline=False)
        self.assert_within_budget(bridge.compact_job(copy.deepcopy(manifest)))

    def test_multi_error_results_fit(self):
        manifest = build_manifest(build_result(120, failed=True), 120)
        self.assert_within_budget(bridge.compact_job(copy.deepcopy(manifest)))

    def test_eighty_component_recolor_fits(self):
        manifest = build_manifest(build_recolor_result(80), 2)
        compact = bridge.compact_job(copy.deepcopy(manifest))
        self.assert_within_budget(compact)
        # Counts and verification status stay; the 80 readbacks are not inlined.
        self.assertEqual(compact["result"]["recolor"]["painted"], 80)
        self.assertLessEqual(utf8_bytes(compact["result"]["recolor"]), 1024)

    def test_total_and_truncation_markers_survive_the_trim(self):
        manifest = build_manifest(build_result(60), 60)
        result = bridge.compact_job(copy.deepcopy(manifest))["result"]
        self.assertEqual(result["operations_total"], 60)
        self.assertTrue(result["operations_truncated"])
        counts = result["operations_status_counts"]
        self.assertEqual(sum(counts.values()), 60)
        self.assertEqual(counts["succeeded"], 60)
        self.assertLessEqual(len(result["operations"]), SAMPLE_LIMIT)

    def test_a_small_job_keeps_every_operation_record(self):
        manifest = build_manifest(build_result(12), 12)
        result = bridge.compact_job(copy.deepcopy(manifest))["result"]
        self.assertEqual(result["operations_total"], 12)
        self.assertFalse(result["operations_truncated"])
        self.assertEqual(len(result["operations"]), 12)

    def test_the_failed_record_keeps_its_failure_reason_after_the_trim(self):
        result = build_result(60, polyline=False, failed=True)
        # Fail deep in the plan so the record sits outside the sample window.
        result["failed_operation_index"] = 55
        for index in (3, 5, 7, 55):
            result["operations"][index]["succeeded"] = False
            result["operations"][index]["execution_status"] = "failed"
            result["operations"][index]["effect_status"] = "rolled_back"
            result["operations"][index]["message"] = f"failure reason at {index}"
            result["operations"][index]["feature_errors"] = feature_errors_block()
        manifest = build_manifest(result, 60, polyline=False)
        compact = bridge.compact_job(copy.deepcopy(manifest))
        kept = compact["result"]["operations"]
        self.assertTrue(compact["result"]["operations_truncated"])
        failed = [op for op in kept if op.get("index") == 55]
        self.assertEqual(len(failed), 1)
        self.assertEqual(failed[0]["message"], "failure reason at 55")
        self.assertIn("feature_errors", failed[0])

    def test_protected_outcome_evidence_is_never_cut(self):
        manifest = build_manifest(build_result(120, failed=True), 120)
        compact = bridge.compact_job(copy.deepcopy(manifest))
        result = compact["result"]
        for key in (
            "message",
            "toolkit_code",
            "failed_stage",
            "failed_toolkit_call",
            "failed_operation_index",
            "rollback_succeeded",
            "model_unchanged",
            "rollback_message",
            "rollback_code",
            "saved_file_reloaded_and_verified",
            "sha256",
            "part_file",
        ):
            with self.subTest(key=key):
                self.assertIn(key, result)
        self.assertEqual(result["failed_operation_index"], 3)
        self.assertTrue(result["saved_file_reloaded_and_verified"])
        self.assertEqual(result["sha256"], "a" * 64)
        self.assertEqual(compact["revision"], 7)

    def test_an_oversized_protected_value_reports_the_real_size(self):
        result = build_result(4)
        result["message"] = "x" * (40 * 1024)  # a failure reason alone over budget
        manifest = build_manifest(result, 4)
        compact = bridge.compact_job(copy.deepcopy(manifest))
        self.assertEqual(compact["result"]["message"], result["message"])
        budget = compact["result"]["result_budget"]
        self.assertTrue(budget["exceeded"])
        self.assertEqual(budget["budget_bytes"], RESPONSE_BUDGET)
        self.assertGreater(budget["serialized_bytes"], RESPONSE_BUDGET)

    def test_session_erase_remaining_after_lists_are_bounded(self):
        # The shape that overflowed real 0.11.0 jobs: a 240-entry pass-through
        # list inside a result block.
        result = build_result(4)
        result["session_erase"] = {
            "action": "erase",
            "erased": ["one"],
            "message": "Session models erased; nothing was saved or deleted on disk",
            "remaining_after": [
                {"model_id": f"{i:032x}", "model_name": f"m{i:03d}", "model_type": "part"}
                for i in range(240)
            ],
            "stopped_early": False,
        }
        manifest = build_manifest(result, 4)
        compact = bridge.compact_job(copy.deepcopy(manifest))
        self.assert_within_budget(compact)
        remaining = compact["result"]["session_erase"]["remaining_after"]
        self.assertEqual(remaining["total"], 240)
        self.assertTrue(remaining["truncated"])
        self.assertEqual(len(remaining["sample"]), SAMPLE_LIMIT)
        self.assertEqual(compact["result"]["session_erase"]["action"], "erase")


class BoundedSummaryTests(unittest.TestCase):
    """One shared bounded-summary contract for the new diagnostics."""

    def test_diagnostic_blocks_are_re_capped_with_totals(self):
        block = {
            "available": True,
            "max_deviation_mm": 0.0012,
            "total": 37,
            "truncated": False,
            "sample": [{"entity": f"e{i}", "deviation_mm": 0.001} for i in range(37)],
        }
        projected = bounded_summary(block)
        self.assertEqual(projected["total"], 37)
        self.assertTrue(projected["truncated"])
        self.assertEqual(len(projected["sample"]), SAMPLE_LIMIT)
        self.assertEqual(projected["max_deviation_mm"], 0.0012)

    def test_feature_errors_keep_the_producer_total_and_sample_shape(self):
        block = feature_errors_block(37)
        projected = bounded_summary(block)
        self.assertEqual(projected["element_errors"]["total"], 37)
        self.assertTrue(projected["element_errors"]["truncated"])
        self.assertEqual(len(projected["element_errors"]["sample"]), SAMPLE_LIMIT)
        self.assertEqual(projected["failed_stage"], "CompleteFeature")

    def test_failed_model_cleanup_receipts_pass_through(self):
        receipt = {
            "attempted": True,
            "status": "erased",
            "reason": "absence verified",
            "erase_code": 0,
            "absence_verified": True,
        }
        self.assertEqual(bounded_summary(receipt), receipt)

    def test_small_values_keep_their_exact_shape(self):
        value = {
            "near_tolerance_pairs": {
                "total": 2,
                "truncated": False,
                "sample": [{"entities": ["a", "b"], "gap_mm": 0.001}],
            },
            "origin": [0, 0, 0],
            "labels": ["x", "y"],
            "scalar": 3,
        }
        self.assertEqual(bounded_summary(value), value)

    def test_plain_long_lists_carry_the_same_marker_shape(self):
        projected = bounded_summary({"points": [[i, i] for i in range(81)]})
        points = projected["points"]
        self.assertEqual(points["total"], 81)
        self.assertTrue(points["truncated"])
        self.assertEqual(len(points["sample"]), SAMPLE_LIMIT)

    def test_unknown_totals_are_never_invented(self):
        block = {"sample": list(range(37)), "truncated": True}
        projected = bounded_summary(block)
        self.assertNotIn("total", projected)
        self.assertTrue(projected["truncated"])
        self.assertEqual(len(projected["sample"]), SAMPLE_LIMIT)

    def test_the_budget_enforcer_is_idempotent_for_small_summaries(self):
        summary = {"result": {"operations": [sketch_op_record(0)]}}
        once = enforce_compact_budget(copy.deepcopy(summary))
        self.assertEqual(once, summary)


class FullPaginationTests(unittest.TestCase):
    """detail=full: whole view for small jobs, pages for the rest."""

    def small_manifest(self) -> dict:
        return build_manifest(build_result(2), 2)

    def large_manifest(self) -> dict:
        return build_manifest(build_result(60), 60)

    def test_small_jobs_keep_the_whole_full_view(self):
        manifest = self.small_manifest()
        view = job_page(manifest)
        self.assertTrue(view["complete"])
        self.assertIsNone(view["next_cursor"])
        self.assertEqual(view["result"]["operations"], manifest["result"]["operations"])
        self.assertEqual(view["operations"], manifest["operations"])

    def test_large_jobs_page_instead_of_echoing_everything(self):
        manifest = self.large_manifest()
        page = job_page(manifest)
        self.assertFalse(page["complete"])
        self.assertIsNotNone(page["next_cursor"])
        self.assertEqual(page["detail"], "full")
        self.assertEqual(page["section_counts"]["operations_input"], 60)
        self.assertLessEqual(utf8_bytes(page), RESPONSE_BUDGET)
        # The input echo is not returned unbounded with the first page.
        self.assertLess(len(page["data"]["operations_input"]), 60)

    def test_every_page_stays_inside_the_budget(self):
        manifest = self.large_manifest()
        cursor = None
        pages = 0
        while True:
            page = job_page(manifest, limit=10, cursor=cursor)
            self.assertLessEqual(utf8_bytes(page), RESPONSE_BUDGET)
            pages += 1
            cursor = page["next_cursor"]
            if cursor is None:
                self.assertTrue(page["complete"])
                break
            self.assertLess(pages, 200)
        self.assertGreater(pages, 1)

    def test_missing_pages_stay_retrievable(self):
        # Terminal job manifests are immutable, so a cursor keeps working:
        # a lost page can be fetched again before continuing.
        manifest = self.large_manifest()
        first = job_page(manifest, limit=5)
        cursor = first["next_cursor"]
        again = job_page(manifest, limit=5, cursor=cursor)
        repeated = job_page(manifest, limit=5, cursor=cursor)
        self.assertEqual(again["data"], repeated["data"])
        self.assertEqual(again["next_cursor"], repeated["next_cursor"])

    def test_pages_reassemble_the_same_records_as_the_whole_view(self):
        manifest = self.large_manifest()
        collected: dict[str, list] = {name: [] for name in SECTIONS}
        page = job_page(manifest, limit=7)
        for name in SECTIONS:
            collected[name].extend(page["data"][name])
        cursor = page["next_cursor"]
        while cursor is not None:
            page = job_page(manifest, limit=7, cursor=cursor)
            for name in SECTIONS:
                collected[name].extend(page["data"][name])
            cursor = page["next_cursor"]
        for name in SECTIONS:
            with self.subTest(section=name):
                self.assertEqual(collected[name], section_records(manifest, name))

    def test_one_section_can_be_paged_alone(self):
        manifest = self.large_manifest()
        page = job_page(manifest, section="operations_result", limit=5)
        self.assertEqual(list(page["data"]), ["operations_result"])
        self.assertEqual(page["total"], 60)
        self.assertEqual(page["returned_count"], 5)
        self.assertEqual([op["index"] for op in page["data"]["operations_result"]], [0, 1, 2, 3, 4])

    def test_result_entries_expose_the_full_receipts_leaf_by_leaf(self):
        result = build_result(8, failed=True)
        manifest = build_manifest(result, 8)
        entries = section_records(manifest, "result_entries")
        paths = [entry["path"] for entry in entries]
        self.assertIn("result.feature_errors.element_errors.total", paths)
        # operation records have their own section; they are not leaf-walked here
        self.assertNotIn("result.operations[0]", paths)
        self.assertIn("revision", paths)
        values = {entry["path"]: entry["value"] for entry in entries}
        self.assertEqual(values["revision"], 7)
        self.assertEqual(values["result.feature_errors.element_errors.total"], 37)

    def test_cursors_bind_to_the_job_snapshot_and_section(self):
        manifest = self.large_manifest()
        page = job_page(manifest, limit=5)
        cursor = page["next_cursor"]
        with self.assertRaises(ValueError):
            job_page(manifest, section="operations_result", limit=5, cursor=cursor)
        tampered = dict(manifest)
        tampered["status"] = "failed"
        with self.assertRaises(ValueError):
            job_page(tampered, limit=5, cursor=cursor)
        with self.assertRaises(ValueError):
            job_page(manifest, limit=5, cursor="broken")

    def test_limits_and_sections_are_validated(self):
        manifest = self.small_manifest()
        with self.assertRaises(ValueError):
            job_page(manifest, limit=0)
        with self.assertRaises(ValueError):
            job_page(manifest, limit=500)
        with self.assertRaises(ValueError):
            job_page(manifest, section="no_such_section")

    def test_an_oversize_leaf_is_marked_not_cut(self):
        result = build_result(2)
        result["enormous_note"] = "y" * (ENTRY_BUDGET + 1024)
        manifest = build_manifest(result, 2)
        page = job_page(manifest, section="result_entries", limit=50)
        oversize = [entry for entry in page["data"]["result_entries"] if entry.get("oversize")]
        self.assertTrue(oversize)
        self.assertEqual(oversize[0]["path"], "result.enormous_note")
        self.assertGreater(oversize[0]["size_hint_bytes"], ENTRY_BUDGET)
        # The source stays readable through its own record, not through a cut.
        self.assertNotIn("value", oversize[0])

    def test_compact_rejects_section_and_cursor(self):
        with self.assertRaises(ValueError):
            bridge.get_job("b" * 32, "compact", section="result_entries")

    def test_decode_round_trip_keeps_the_offset(self):
        manifest = self.large_manifest()
        page = job_page(manifest, limit=5)
        token = decode_cursor(page["next_cursor"])
        self.assertEqual(token["offset"], 5)
        self.assertEqual(token["job_id"], "b" * 32)


if __name__ == "__main__":
    unittest.main()
