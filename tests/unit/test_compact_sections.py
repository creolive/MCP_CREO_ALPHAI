"""FEAT-023/FEAT-008 (Q06/R04): optional ``sections`` projection for compact jobs.

Offline coverage only; nothing connects to Creo. The contract frozen here:

- omitted ``sections`` keeps the exact pre-feature compact payload;
- a named block is the only detail that survives; unnamed blocks are absent
  and the response reports ``sections_applied``/``omitted_sections``;
- an unknown name is rejected before the job directory is read and the job
  file stays byte-identical;
- the 32 KiB budget and the operation sample cap still apply after the
  projection;
- ``detail=full`` is untouched and rejects ``sections``.
"""

from __future__ import annotations

import copy
import json
import shutil
import tempfile
import unittest
from pathlib import Path
from unittest import mock

import bridge
from creo_mechdog.compact_sections import known_sections, resolve_sections
from creo_mechdog.job_projection import LIST_ITEM_BUDGET
from creo_mechdog.model_queries import RESPONSE_BUDGET, serialized_size

JOB_ID = "a" * 32


def _sample_block(name: str, size: int = 20) -> dict:
    return {
        "available": True,
        name: {
            "total": size,
            "truncated": False,
            "sample": [
                {"entity": f"e{index}", "deviation_mm": 0.000001, "reason": None}
                for index in range(size)
            ],
        },
    }


def _operation(index: int) -> dict:
    op = "sketch" if index % 2 == 0 else "extrude"
    return {
        "op": op,
        "index": index,
        "label": f"op_{index:03d}",
        "succeeded": True,
        "execution_status": "succeeded",
        "effect_status": "committed",
        "message": "ok",
        "profile": {
            "source": "input",
            "analysis": "closed",
            "entity_count": 81,
            "near_tolerance_pairs": {
                "total": 20,
                "truncated": False,
                "sample": [
                    {"entities": [f"e{j}", f"e{j + 1}"], "gap_mm": 0.00011} for j in range(20)
                ],
            },
        },
        "native_section": {
            "available": True,
            "closed_contours": 1,
            "contours": 1,
            "entities": 81,
            "open_ends": 0,
        },
        "preview": {"path": f"preview_{index}.jpg", "width": 640, "height": 480, "bytes": 23111},
        "parameters": {"depth": 25.0, "direction": "positive", "draft_angle": 0.0},
        "metadata": {"note": "input echo kept for one polling round", "request_id": index},
        "extrude_depth": {
            "source": "feature_tree",
            "query_code": 0,
            "requested_depth_type": "blind",
            "requested_depth_mm": 25.0,
            "effective_depth_type": "blind",
            "effective_depth_mm": 25.0,
            "defaulted_fields": [],
        },
        "geometry_deviation": _sample_block("entities"),
        "volume_before_mm3": 1000.0,
        "volume_after_mm3": 6000.0,
        "material_delta_mm3": 5000.0,
    }


def build_manifest(count: int = 6) -> dict:
    operations = [_operation(index) for index in range(count)]
    result = {
        "success": True,
        "message": "ok",
        "code": 0,
        "toolkit_code": 0,
        "part_file": r"E:\jobs\aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa\output\model.prt.1",
        "sha256": "b" * 64,
        "saved_file_reloaded_and_verified": True,
        "rollback_succeeded": None,
        "rollback_status": "not_attempted",
        "model_unchanged": None,
        "preview_file": r"E:\jobs\aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa\output\preview.jpg",
        "preview_status": "written",
        "preview_code": 0,
        "preview": {
            "path": "preview.jpg",
            "width": 1280,
            "height": 960,
            "bytes": 120000,
        },
        "connected": True,
        "volume_mm3": 60318.57,
        "expected_volume_mm3": 60318.57,
        "extrude_count": 3,
        "round_count": 0,
        "hole_count": 0,
        "inspection_source": "saved_reloaded",
        "inspection": {
            "healthy": True,
            "has_solid": True,
            "units": "mm",
            "features": [{"id": index, "name": f"f_{index}"} for index in range(20)],
        },
        "geometry_deviation": _sample_block("entities"),
        "operations": operations,
    }
    inputs = [
        {"op": "sketch" if index % 2 == 0 else "extrude", "label": f"op_{index:03d}"}
        for index in range(count)
    ]
    return {
        "job_id": JOB_ID,
        "kind": "generic",
        "model_id": "c" * 32,
        "status": "succeeded",
        "stage": "verified",
        "revision": 7,
        "readonly": False,
        "created_at": "2026-11-06T00:00:00+00:00",
        "finished_at": "2026-11-06T00:01:00+00:00",
        "message": "Native PRT saved, reloaded and verified",
        "operations": inputs,
        "result": result,
    }


def utf8_bytes(value) -> int:
    return len(json.dumps(value, ensure_ascii=False).encode("utf-8"))


class DefaultBehaviorTests(unittest.TestCase):
    def test_omitted_sections_keeps_the_pre_feature_payload(self):
        manifest = build_manifest()
        baseline = bridge.compact_job(copy.deepcopy(manifest))
        explicit_none = bridge.compact_job(copy.deepcopy(manifest), None)
        self.assertEqual(baseline, explicit_none)
        self.assertNotIn("sections_applied", baseline)
        self.assertNotIn("omitted_sections", baseline)
        result = baseline["result"]
        for key in ("preview", "inspection", "geometry_deviation", "operations"):
            with self.subTest(key=key):
                self.assertIn(key, result)
        # Every compact operation record still carries the full detail set.
        record = result["operations"][1]
        for key in ("profile", "parameters", "preview", "extrude_depth"):
            with self.subTest(key=key):
                self.assertIn(key, record)

    def test_empty_selection_keeps_only_outcome_evidence(self):
        manifest = build_manifest()
        projected = bridge.compact_job(copy.deepcopy(manifest), sections=[])
        result = projected["result"]
        self.assertEqual(projected["sections_applied"], [])
        self.assertEqual(
            projected["omitted_sections"],
            sorted({"preview", "inspection", "geometry_deviation", "operations"}),
        )
        self.assertEqual(
            sorted(result),
            sorted(
                [
                    "success",
                    "message",
                    "code",
                    "toolkit_code",
                    "part_file",
                    "sha256",
                    "saved_file_reloaded_and_verified",
                    "rollback_succeeded",
                    "rollback_status",
                    "model_unchanged",
                    "preview_file",
                    "preview_status",
                    "preview_code",
                    "connected",
                    "volume_mm3",
                    "expected_volume_mm3",
                    "extrude_count",
                    "round_count",
                    "hole_count",
                    "inspection_source",
                    "operations_total",
                    "operations_truncated",
                ]
            ),
        )


class SectionProjectionTests(unittest.TestCase):
    def test_single_block_keeps_only_that_block(self):
        manifest = build_manifest()
        projected = bridge.compact_job(copy.deepcopy(manifest), sections=["geometry_deviation"])
        self.assertEqual(projected["sections_applied"], ["geometry_deviation"])
        result = projected["result"]
        self.assertIn("geometry_deviation", result)
        self.assertNotIn("preview", result)
        self.assertNotIn("inspection", result)
        # ``operations`` survives because a per-operation block was named, but
        # each record keeps identity and the named block only.
        record = result["operations"][0]
        self.assertIn("geometry_deviation", record)
        self.assertEqual(record["index"], 0)
        self.assertEqual(record["op"], "sketch")
        for key in ("profile", "parameters", "preview", "native_section"):
            with self.subTest(key=key):
                self.assertNotIn(key, record)
        omitted = projected["omitted_sections"]
        for key in ("preview", "inspection", "profile", "parameters", "extrude_depth"):
            with self.subTest(key=key):
                self.assertIn(key, omitted)

    def test_named_operations_keep_the_pre_feature_records(self):
        manifest = build_manifest()
        projected = bridge.compact_job(copy.deepcopy(manifest), sections=["operations"])
        self.assertEqual(projected["sections_applied"], ["operations"])
        result = projected["result"]
        self.assertIn("operations", result)
        record = result["operations"][0]
        for key in ("profile", "parameters", "preview", "extrude_depth"):
            with self.subTest(key=key):
                self.assertIn(key, record)
        self.assertNotIn("preview", result)
        self.assertNotIn("inspection", result)
        self.assertIn("preview", projected["omitted_sections"])
        self.assertIn("inspection", projected["omitted_sections"])

    def test_unknown_block_is_rejected_before_the_job_is_read(self):
        with self.assertRaises(ValueError) as caught:
            resolve_sections(["not_a_block"])
        message = str(caught.exception)
        self.assertIn("not_a_block", message)
        for key in ("extrude_depth", "geometry_deviation", "operations", "preview"):
            with self.subTest(key=key):
                self.assertIn(key, message)
        self.assertEqual(known_sections(), sorted(known_sections()))

    def test_projection_shrinks_the_payload(self):
        manifest = build_manifest(6)
        baseline = bridge.compact_job(copy.deepcopy(manifest))
        projected = bridge.compact_job(copy.deepcopy(manifest), sections=["extrude_depth"])
        self.assertLess(utf8_bytes(projected), utf8_bytes(baseline) * 0.6)
        self.assertLess(utf8_bytes(projected), 8192)

    def test_projection_does_not_bypass_the_budget_or_the_sample_cap(self):
        manifest = build_manifest(60)
        projected = bridge.compact_job(copy.deepcopy(manifest), sections=["operations"])
        self.assertLessEqual(utf8_bytes(projected), RESPONSE_BUDGET)
        result = projected["result"]
        self.assertEqual(result["operations_total"], 60)
        self.assertTrue(result["operations_truncated"])
        self.assertLessEqual(len(result["operations"]), 20)
        status_counts = result["operations_status_counts"]
        self.assertEqual(sum(status_counts.values()), 60)


class JobQueryTests(unittest.TestCase):
    def setUp(self):
        self.root = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, self.root, ignore_errors=True)
        self._jobs = bridge.JOBS
        bridge.JOBS = self.root
        self.addCleanup(setattr, bridge, "JOBS", self._jobs)
        manifest = build_manifest()
        (self.root / JOB_ID).mkdir(parents=True)
        bridge.write_json(self.root / JOB_ID / "job.json", manifest)
        self.manifest_path = self.root / JOB_ID / "job.json"

    def test_unknown_sections_do_not_touch_the_job(self):
        before = self.manifest_path.read_bytes()
        with mock.patch.object(bridge, "job_path", side_effect=AssertionError("job read")):
            with self.assertRaises(ValueError) as caught:
                bridge.get_job(JOB_ID, "compact", sections=["missing_block"])
        self.assertIn("missing_block", str(caught.exception))
        self.assertEqual(self.manifest_path.read_bytes(), before)
        self.assertEqual([p.name for p in self.root.iterdir()], [JOB_ID])

    def test_compact_query_applies_the_selection(self):
        job = bridge.get_job(JOB_ID, "compact", sections=["preview"])
        self.assertEqual(job["sections_applied"], ["preview"])
        self.assertIn("preview", job["result"])
        self.assertNotIn("inspection", job["result"])
        self.assertEqual(job["revision"], 7)

    def test_full_detail_is_unaffected_and_rejects_sections(self):
        full = bridge.get_job(JOB_ID)
        self.assertEqual(full["detail"], "full")
        self.assertNotIn("sections_applied", full)
        before = self.manifest_path.read_bytes()
        with self.assertRaises(ValueError) as caught:
            bridge.get_job(JOB_ID, "full", sections=["preview"])
        self.assertIn("detail=compact", str(caught.exception))
        self.assertEqual(self.manifest_path.read_bytes(), before)
        self.assertEqual(bridge.get_job(JOB_ID), full)

    def test_list_jobs_compact_returns_bounded_items_referencing_the_job(self):
        jobs = bridge.list_jobs(limit=5, detail="compact")
        self.assertEqual(len(jobs), 1)
        self.assertEqual(jobs[0]["job_id"], JOB_ID)
        self.assertEqual(jobs[0]["outcome"], "success")
        self.assertNotIn("result", jobs[0])
        self.assertNotIn("sections_applied", jobs[0])
        self.assertLessEqual(serialized_size(jobs[0]), LIST_ITEM_BUDGET)

    def test_list_jobs_still_validates_sections_for_compatibility(self):
        jobs = bridge.list_jobs(limit=5, detail="compact", sections=["preview"])
        self.assertNotIn("result", jobs[0])
        with self.assertRaises(ValueError):
            bridge.list_jobs(limit=5, detail="full", sections=["preview"])


class ToolLayerRejectionTests(unittest.TestCase):
    """The MCP tools surface a rejected selection as a tool error, not a job."""

    def assert_tool_error(self, coroutine):
        import asyncio

        from mcp.server.mcpserver.exceptions import ToolError

        with self.assertRaises(ToolError) as caught:
            asyncio.run(coroutine)
        self.assertIn("missing_block", str(caught.exception))
        self.assertIn("preview", str(caught.exception))

    def test_get_job_rejects_an_unknown_section(self):
        import server

        self.assert_tool_error(
            server.creo_get_job(JOB_ID, "compact", None, 50, None, ["missing_block"])
        )

    def test_list_jobs_rejects_an_unknown_section(self):
        import server

        self.assert_tool_error(server.creo_list_jobs(10, "compact", ["missing_block"]))


if __name__ == "__main__":
    unittest.main()
