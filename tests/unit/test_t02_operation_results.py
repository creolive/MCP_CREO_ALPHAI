"""DEV-047 T02: one terminal operation result per input, execution vs effect."""

from __future__ import annotations

import copy
import subprocess
import tempfile
import unittest
from contextlib import ExitStack
from pathlib import Path
from unittest.mock import patch

import bridge
import generic_bridge as general
from creo_mechdog import model_registry
from creo_mechdog.operation_results import (
    EFFECT_STATUSES,
    EXECUTION_STATUSES,
    annotate_native_result,
    normalize_operations,
)

NATIVE = Path(__file__).resolve().parents[2] / "native"


def native_source(name: str) -> str:
    return (NATIVE / name).read_text(encoding="utf-8")


class NativeCollectorContract(unittest.TestCase):
    """Offline guard: no branch appends a result beside the shared tail."""

    def test_only_the_collector_appends_operation_results(self):
        # The duplicate-operation defect came from a branch and the common tail
        # both appending. One collector keeps the invariant cheap to check.
        self.assertEqual(native_source("generic.cpp").count("operation_results.push_back"), 1)
        for path in sorted(NATIVE.glob("*.cpp")):
            if path.name == "generic.cpp":
                continue
            with self.subTest(path=path.name):
                self.assertNotIn("operation_results.push_back", path.read_text(encoding="utf-8"))

    def test_every_operation_path_stages_its_detail(self):
        for name in (
            "generic.cpp",
            "drawing.cpp",
            "placement.cpp",
            "sketch_edit.cpp",
            "surfaces.cpp",
            "udf.cpp",
        ):
            with self.subTest(path=name):
                self.assertIn("stage_operation_result", native_source(name))
        seed = native_source("loft_seed.cpp")
        # The seed rebinding is plan-level construction, not an input operation.
        self.assertNotIn("stage_operation_result", seed)
        self.assertIn('"loft_seed_feature"', native_source("generic.cpp"))

    def test_generated_names_do_not_depend_on_the_result_count(self):
        for name in ("advanced.cpp", "drawing.cpp"):
            with self.subTest(path=name):
                source = native_source(name)
                self.assertNotIn("operation_results.size()", source)
                self.assertIn("generated_identity_index()", source)

    def test_finalizer_covers_not_executed_and_uses_zero_based_index(self):
        source = native_source("generic.cpp")
        self.assertIn("finalize_operation_results", source)
        for token in (
            '"not_executed"',
            '"no_effect"',
            '"rolled_back"',
            '"committed"',
            '"execution_status"',
            '"effect_status"',
            '"index", index',
        ):
            with self.subTest(token=token):
                self.assertIn(token, source)

    def test_unchanged_stays_on_the_two_verified_shortcuts(self):
        # unchanged=true is only the verified same-geometry sketch shortcut and
        # the no-op reorder; same-value set_dimensions does not gain it.
        owners = {
            path.name
            for path in NATIVE.glob("*.cpp")
            if '"unchanged"' in path.read_text(encoding="utf-8")
        }
        self.assertEqual(owners, {"placement.cpp", "sketch_edit.cpp"})
        self.assertIn("native_geometry_verified", native_source("sketch_edit.cpp"))
        self.assertNotIn('"unchanged"', native_source("generic.cpp"))


class NormalizeProjection(unittest.TestCase):
    def test_native_statuses_are_authoritative_and_never_upgraded(self):
        operations = [
            {
                "op": "extrude",
                "index": 0,
                "succeeded": True,
                "execution_status": "unknown",
                "effect_status": "unknown",
            }
        ]
        normalized = normalize_operations(operations, job_status="succeeded", readonly=False)
        self.assertEqual(normalized[0]["execution_status"], "unknown")
        self.assertEqual(normalized[0]["effect_status"], "unknown")

    def test_successful_writable_plan_commits_and_readonly_does_not_write(self):
        operations = [{"op": "export", "index": 0, "succeeded": True}]
        committed = normalize_operations(operations, job_status="succeeded")
        self.assertEqual(committed[0]["effect_status"], "committed")
        readonly = normalize_operations(operations, job_status="succeeded", readonly=True)
        self.assertEqual(readonly[0]["effect_status"], "no_effect")

    def test_first_and_middle_failures_keep_the_failed_position(self):
        for failed in (0, 1):
            with self.subTest(failed=failed):
                operations = [
                    {"op": f"op{index}", "index": index, "succeeded": index < failed}
                    for index in range(3)
                ]
                normalized = normalize_operations(
                    operations, job_status="failed", failed_index=failed
                )
                self.assertEqual(
                    [item["execution_status"] for item in normalized],
                    [
                        "succeeded"
                        if index < failed
                        else "failed"
                        if index == failed
                        else "unknown"
                        for index in range(3)
                    ],
                )

    def test_rollback_requires_evidence_and_marks_executed_items(self):
        operations = [{"op": "extrude", "index": 0, "succeeded": True}]
        unproven = normalize_operations(operations, job_status="failed")
        self.assertEqual(unproven[0]["effect_status"], "unknown")
        proven = normalize_operations(operations, job_status="failed", rollback_confirmed=True)
        self.assertEqual(proven[0]["effect_status"], "rolled_back")

    def test_not_executed_stays_no_effect_and_never_commits(self):
        operations = [
            {"op": "sketch", "index": 0, "execution_status": "not_executed", "succeeded": False}
        ]
        normalized = normalize_operations(operations, job_status="failed", rollback_confirmed=True)
        self.assertEqual(normalized[0]["execution_status"], "not_executed")
        self.assertEqual(normalized[0]["effect_status"], "no_effect")

    def test_unknown_execution_is_not_reported_as_success(self):
        normalized = normalize_operations(
            [{"op": "extrude", "index": 0, "succeeded": False}], job_status="failed"
        )
        self.assertEqual(normalized[0]["execution_status"], "unknown")
        self.assertEqual(normalized[0]["effect_status"], "unknown")

    def test_index_is_backfilled_and_empty_results_are_not_fabricated(self):
        normalized = normalize_operations(
            [{"op": "a", "succeeded": True}, {"op": "b", "succeeded": True}],
            job_status="succeeded",
        )
        self.assertEqual([item["index"] for item in normalized], [0, 1])
        self.assertEqual(normalize_operations(None, job_status="failed"), [])
        self.assertNotIn("operations", annotate_native_result({"success": False}, readonly=False))

    def test_status_vocabularies_are_closed(self):
        self.assertEqual(
            set(EXECUTION_STATUSES), {"succeeded", "failed", "not_executed", "unknown"}
        )
        self.assertEqual(set(EFFECT_STATUSES), {"committed", "rolled_back", "no_effect", "unknown"})


class RunJobProjection(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory(prefix="dev047_t02_")
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name).resolve()
        (self.root / "jobs").mkdir()
        (self.root / "models").mkdir()
        stack = ExitStack()
        self.addCleanup(stack.close)
        for obj, name, value in (
            (bridge, "ROOT", self.root),
            (bridge, "JOBS", self.root / "jobs"),
            (general, "MODELS", self.root / "models"),
        ):
            stack.enter_context(patch.object(obj, name, value))
        stack.enter_context(
            patch.object(bridge, "build_native", return_value=self.root / "worker.exe")
        )
        self.model_id = "d" * 32
        path = general.model_path(self.model_id)
        (path / "output").mkdir(parents=True)
        self.part = path / "output" / "plate.prt.1"
        self.part.write_bytes(b"native part bytes")
        model = {
            "model_id": self.model_id,
            "model_name": "plate",
            "revision": 1,
            "status": "ready",
            "model_type": "part",
            "aliases": {},
            "inspection": {"features": []},
            "part_file": str(self.part),
            "output_directory": str(path / "output"),
        }
        model_registry.write_model(path, model)
        self.job_id = "e" * 32
        directory = bridge.job_path(self.job_id)
        (directory / "output").mkdir(parents=True)
        self.operations = [
            {"op": "extrude", "label": "boss"},
            {"op": "round", "label": "edge_round", "size": 2},
            {"op": "hole", "label": "hole_1"},
        ]
        self.request = {
            "new": False,
            "model": {k: model[k] for k in ("model_id", "model_name", "model_type", "revision")},
            "operations": self.operations,
            "readonly": False,
            "components": {},
        }
        bridge.write_json(directory / "request.json", self.request)
        self.manifest = {"job_id": self.job_id, "kind": "generic", "model_id": self.model_id}
        bridge.write_json(directory / "job.json", self.manifest)

    def run_worker(self, result):
        directory = bridge.job_path(self.job_id)

        def fake_run(*args, **kwargs):
            bridge.write_json(directory / "native_result.json", result)
            return subprocess.CompletedProcess([], 0)

        with (
            patch.object(bridge.subprocess, "run", side_effect=fake_run),
            patch.object(bridge, "native_environment", return_value={}),
            patch.object(bridge, "note_native_outcome", return_value=None),
            patch.object(bridge, "config", return_value={}),
        ):
            general.run_generic_job(self.job_id, copy.deepcopy(self.manifest))
        return bridge.read_json(directory / "job.json")

    def test_success_keeps_n_results_and_one_revision(self):
        result = {
            "success": True,
            "delivery_complete": True,
            "disconnect_code": 0,
            "saved_file_reloaded_and_verified": True,
            "part_file": str(self.part),
            "aliases": {},
            "inspection": {"features": []},
            "operations": [
                {"op": op["op"], "index": index, "succeeded": True}
                for index, op in enumerate(self.operations)
            ],
        }
        manifest = self.run_worker(result)
        self.assertEqual(manifest["status"], "succeeded")
        self.assertEqual(manifest["revision"], 2)
        operations = manifest["result"]["operations"]
        self.assertEqual([item["index"] for item in operations], [0, 1, 2])
        self.assertEqual([item["effect_status"] for item in operations], ["committed"] * 3)

    def test_failure_keeps_executed_failed_and_not_executed(self):
        result = {
            "success": False,
            "delivery_complete": True,
            "disconnect_code": 0,
            "toolkit_code": 1,
            "message": "boolean failed",
            "rollback_succeeded": True,
            "failed_operation_index": 1,
            "part_file": str(self.part),
            "aliases": {},
            "inspection": None,
            "operations": [
                {
                    "op": "extrude",
                    "index": 0,
                    "succeeded": True,
                    "execution_status": "succeeded",
                    "effect_status": "rolled_back",
                },
                {
                    "op": "round",
                    "index": 1,
                    "succeeded": False,
                    "execution_status": "failed",
                    "effect_status": "rolled_back",
                },
                {
                    "op": "hole",
                    "index": 2,
                    "succeeded": False,
                    "execution_status": "not_executed",
                    "effect_status": "no_effect",
                },
            ],
        }
        manifest = self.run_worker(result)
        self.assertEqual(manifest["status"], "failed")
        # A failed plan does not advance the model revision.
        self.assertEqual(general.model_info(self.model_id)["revision"], 1)
        operations = manifest["result"]["operations"]
        self.assertEqual(len(operations), len(self.operations))
        self.assertEqual(
            [item["execution_status"] for item in operations],
            ["succeeded", "failed", "not_executed"],
        )
        self.assertEqual(
            [item["effect_status"] for item in operations],
            ["rolled_back", "rolled_back", "no_effect"],
        )

    def test_legacy_failure_without_rollback_evidence_stays_unknown(self):
        result = {
            "success": False,
            "delivery_complete": True,
            "disconnect_code": 0,
            "toolkit_code": 1,
            "part_file": str(self.part),
            "operations": [{"op": "extrude", "index": 0, "succeeded": True}],
        }
        manifest = self.run_worker(result)
        operation = manifest["result"]["operations"][0]
        self.assertEqual(operation["execution_status"], "succeeded")
        self.assertEqual(operation["effect_status"], "unknown")

    def test_missing_native_operations_are_not_fabricated(self):
        result = {
            "success": False,
            "delivery_complete": True,
            "disconnect_code": 0,
            "toolkit_code": 1,
            "part_file": str(self.part),
        }
        manifest = self.run_worker(result)
        self.assertNotIn("operations", manifest["result"])


class CompactProjection(unittest.TestCase):
    def test_compact_keeps_statuses_and_specialized_fields(self):
        operation = {
            "op": "update_sketch_geometry",
            "index": 0,
            "label": "profile",
            "succeeded": True,
            "execution_status": "succeeded",
            "effect_status": "committed",
            "unchanged": True,
            "native_geometry_verified": True,
            "feature_id": 17,
            "preserved_feature_id": 17,
            "file": "output/part.prt.1",
            "size": 2.5,
            "metadata": {"references": []},
            "material_removed_mm3": 12.0,
            "surface_id": 163,
            "origin": [0, 0, 0],
            "normal": [1, 0, 0],
            "u_axis": [0, 0, 1],
            "v_axis": [0, 1, 0],
            "datum_axes": [],
            "axes_query_code": 0,
            "length_unit": {"name": "mm", "query_code": 0, "scale_to_mm": 1.0},
        }
        compact = bridge.compact_job({"result": {"operations": [operation]}})
        self.assertEqual(compact["result"]["operations"], [operation])


if __name__ == "__main__":
    unittest.main()
