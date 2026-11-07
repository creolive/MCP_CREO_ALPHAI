"""DEV-047 T07: one shared preview step; capture failure stays beside the save.

Offline coverage only. The native assertions read the sources that the single
translation unit (native/worker.cpp) compiles, so a second screenshot path that
bypasses the shared step fails here; nothing connects to Creo.

The driver coverage added for BUG-088/BUG-066 is asserted here as well: the
empty new part is recorded instead of being asserted as a written capture, the
run writes a unique report and image directory, and an existing report is
never overwritten.
"""

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
from creo_mechdog.preview import apply_preview_projection, normalize_preview
from tools import test_t07_preview as driver

NATIVE = Path(__file__).resolve().parents[2] / "native"
SCREENSHOT_PATHS = ("worker.cpp", "generic.cpp", "drawing.cpp")


def native_source(name: str) -> str:
    return (NATIVE / name).read_text(encoding="utf-8")


def region(source: str, start: str, stop: str) -> str:
    begin = source.index(start)
    return source[begin : source.index(stop, begin)]


def compact(source: str) -> str:
    """Whitespace-free view so source markers survive clang-format line breaks."""
    return "".join(source.split())


class NativeSharedStep(unittest.TestCase):
    """Structural guard: both image paths go through native/preview.h."""

    def test_raster_call_lives_only_in_the_shared_step(self):
        shared = native_source("preview.h")
        self.assertEqual(shared.count("ProRasterFileWrite("), 1)
        for name in SCREENSHOT_PATHS:
            with self.subTest(path=name):
                self.assertNotIn("ProRasterFileWrite", native_source(name))

    def test_screenshot_paths_do_not_repeat_the_capture_sequence(self):
        # ProWindowRefresh is unique to the shared step; the display-only paths
        # (rollback, adoption, open_file) keep their own refit/repaint.
        for name in SCREENSHOT_PATHS:
            with self.subTest(path=name):
                self.assertNotIn("ProWindowRefresh", native_source(name))
        shared = native_source("preview.h")
        for token in (
            "ProWindowRefit(",
            "ProWindowRefresh(",
            "ProWindowRepaint(",
            "ProViewMatrixSet(",
            "ProRasterFileWrite(",
        ):
            with self.subTest(token=token):
                self.assertEqual(shared.count(token), 1)

    def test_export_branches_delegate_instead_of_repeating_the_sequence(self):
        for name, start, stop in (
            ("generic.cpp", 'if (format == "jpeg") {', '} else if (format == "stl")'),
            ("drawing.cpp", '} else if (format == "jpeg") {', "Drawing export supports PDF/JPEG"),
        ):
            with self.subTest(path=name):
                block = region(native_source(name), start, stop)
                self.assertIn("capture_preview(", block)
                for token in ("ProWindowRefit", "ProWindowRepaint", "ProViewMatrixSet"):
                    self.assertNotIn(token, block)

    def test_every_screenshot_site_uses_the_shared_capture(self):
        self.assertEqual(native_source("generic.cpp").count("capture_preview("), 2)
        self.assertEqual(native_source("drawing.cpp").count("capture_preview("), 1)
        self.assertEqual(native_source("worker.cpp").count("capture_preview("), 1)

    def test_automatic_preview_never_throws_or_fails_the_job(self):
        # The job preview records codes; only the requested export may fail.
        source = native_source("generic.cpp")
        block = region(source, '"display_preview"', 'log("BUILD_SUCCESS=1')
        self.assertIn("capture_preview(", block)
        self.assertNotIn("CK(", block)
        self.assertNotIn("throw ", block)
        self.assertIn('{"preview_code", preview.raster_code}', block)
        self.assertIn('{"preview", preview_json}', block)

    def test_both_paths_publish_the_raw_codes(self):
        generic = native_source("generic.cpp")
        self.assertEqual(generic.count('{"preview", preview_json}'), 2)
        drawing = native_source("drawing.cpp")
        self.assertIn('export_detail["preview_code"] = preview.raster_code', drawing)
        self.assertIn('export_detail["preview"] = preview_json', drawing)
        self.assertIn('plate_result["preview"] = preview_report', native_source("worker.cpp"))
        shared = native_source("preview.h")
        for step in (
            "display",
            "window_get",
            "window_model_get",
            "current_set",
            "current_get",
            "activate",
            "view_matrix_set",
            "repaint",
            "raster",
            "failed_step",
        ):
            with self.subTest(step=step):
                self.assertIn(f'"{step}"', shared)

    def test_the_confirmation_stage_records_the_real_filesystem_error(self):
        # BUG-088: after a zero raster code the probe must publish the path
        # shape, existence, size and the actual std::error_code.
        shared = native_source("preview.h")
        for token in (
            "preview_confirm_file",
            "file_check_absolute",
            "file_check_parent_exists",
            "file_check_exists",
            "file_check_regular",
            "file_check_code",
            "error.category().name()",
            "error.message()",
            "is_regular_file",
            "is_directory",
            '"file_check"',
            '"after_raster"',
        ):
            with self.subTest(token=token):
                self.assertIn(token, shared)

    def test_only_a_missing_path_maps_to_not_found(self):
        shared = native_source("preview.h")
        block = region(shared, "if (error || outcome.file_bytes <= 0) {", "// One capture attempt.")
        self.assertIn("preview_is_missing(error)", block)
        self.assertIn("PRO_TK_E_NOT_FOUND", block)
        self.assertIn("PRO_TK_GENERAL_ERROR", block)
        # The previous blanket mapping reported every filesystem failure as a
        # missing file.
        self.assertNotIn("error ? PRO_TK_E_NOT_FOUND", shared)

    def test_the_probe_does_not_retry_the_capture_or_the_job(self):
        shared = native_source("preview.h")
        probe = region(shared, "static void preview_confirm_file", "// One capture attempt.")
        self.assertNotIn("ProRasterFileWrite", probe)
        self.assertNotIn("sleep", probe)
        self.assertLess(
            shared.index("code = ProRasterFileWrite"), shared.index("preview_confirm_file(outcome)")
        )

    def test_the_step_checks_the_target_window_and_file_size(self):
        shared = native_source("preview.h")
        for token in (
            "ProWindowMdlGet",
            "ProWindowCurrentGet",
            "ProViewMatrixGet",
            "file_size",
            "preview_written",
            "output_file",
        ):
            with self.subTest(token=token):
                self.assertIn(token, shared)

    def test_empty_geometry_probe_requires_a_complete_feature_scan(self):
        shared = native_source("preview.h")
        probe = region(
            shared, "static ProError preview_geometry_feature", "static std::string preview_utf8"
        )
        for token in (
            "ProSolidFeatVisit",
            "ProFeatureTypeGet",
            "ProFeatureStatusGet",
            "PRO_FEAT_CSYS",
            "PRO_FEAT_DATUM",
            "PRO_FEAT_DATUM_AXIS",
            "PRO_FEAT_DATUM_POINT",
            "PRO_FEAT_SUPPRESSED",
            "PRO_MDL_PART",
            "PRO_TK_E_NOT_FOUND",
            "geometry_diagnostics::preview_skip(",
            "kind == PRO_MDL_PART, kind == PRO_MDL_ASSEMBLY,",
            "probe.renderable,",
            "&& !probe.unknown",
        ):
            with self.subTest(token=token):
                self.assertIn(token, probe)
        self.assertNotIn("volume", probe.lower())
        self.assertIn('"feature_visit_code", code', probe)
        self.assertIn('"non_datum_feature_count"', probe)
        self.assertIn("probe.unknown || !visit_complete", probe)
        capture = region(
            shared, "static void capture_preview_steps", "static PreviewStepOutcome capture_preview"
        )
        self.assertLess(
            capture.index("preview_has_no_geometry(model, outcome.empty_geometry_basis)"),
            capture.index("bind_model_window(model, outcome)"),
        )


class PreviewProjection(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory(prefix="t07_preview_")
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        (self.root / "output").mkdir()
        self.image = self.root / "output" / "preview.jpg"
        self.image.write_bytes(b"\xff\xd8\xff preview bytes")

    def native_block(self, status: str = "written", raster: int = 0) -> dict:
        return {
            "status": status,
            "path": str(self.image),
            "bytes": 16,
            "window": 3,
            "window_matches_model": True,
            "current_window_matches": True,
            "view_matrix_matches": True,
            "codes": {
                "display": 0,
                "window_get": 0,
                "window_model_get": 0,
                "current_set": 0,
                "current_get": 0,
                "activate": 0,
                "view_matrix_set": 0,
                "view_matrix_get": 0,
                "refit": 0,
                "refresh": 0,
                "repaint": 0,
                "raster": raster,
            },
            "failed_step": None if status == "written" else "raster",
            "failed_code": None if status == "written" else raster,
        }

    def test_written_preview_keeps_the_file_and_codes(self):
        result = {"success": True, "preview_code": 0, "preview": self.native_block()}
        block = normalize_preview(result, directory=self.root)
        self.assertEqual(block["status"], "written")
        self.assertTrue(block["file_verified"])
        self.assertEqual(block["codes"]["raster"], 0)
        self.assertEqual(block["window"], 3)
        self.assertEqual(block["source"], "native")

    def test_failed_preview_is_never_upgraded_by_an_existing_file(self):
        result = {"success": True, "preview_code": -5, "preview": self.native_block("failed", -5)}
        apply_preview_projection(result, directory=self.root)
        self.assertEqual(result["preview_status"], "failed")
        self.assertIsNone(result["preview_file"])
        self.assertEqual(result["preview_code"], -5)
        self.assertEqual(result["preview"]["failed_step"], "raster")

    def test_skipped_preview_does_not_probe_a_stale_file_or_claim_raster(self):
        native = self.native_block("skipped_no_geometry", -1)
        native.update(bytes=-1, failed_step=None, failed_code=None, file_check=None)
        native["codes"] = {key: None for key in native["codes"]}
        result = {"success": True, "preview_code": -1, "preview": native}
        with patch.object(Path, "stat", side_effect=PermissionError(13, "Access denied")) as stat:
            apply_preview_projection(result, directory=self.root)
        stat.assert_not_called()
        self.assertEqual(result["preview_status"], "skipped_no_geometry")
        self.assertEqual(result["preview"]["status"], "skipped_no_geometry")
        self.assertEqual(result["preview"]["codes"]["raster"], None)
        self.assertIsNone(result["preview_code"])
        self.assertIsNone(result["preview_file"])
        self.assertFalse(result["preview"]["file_verified"])
        self.assertIsNone(result["preview"]["verification_error"])
        compact = bridge.compact_job({"status": "succeeded", "kind": "generic", "result": result})
        self.assertEqual(compact["result"]["preview_status"], "skipped_no_geometry")
        self.assertEqual(compact["result"]["preview"]["status"], "skipped_no_geometry")

    def test_claimed_written_image_must_exist_and_be_non_empty(self):
        self.image.unlink()
        result = {"success": True, "preview": self.native_block()}
        block = normalize_preview(result, directory=self.root)
        self.assertEqual(block["status"], "failed")
        self.assertEqual(block["failed_step"], "output_file_verification")
        self.assertFalse(block["file_verified"])

        self.image.write_bytes(b"")
        block = normalize_preview(result, directory=self.root)
        self.assertEqual(block["status"], "failed")

    def test_legacy_raster_code_without_native_block(self):
        result = {"success": True, "preview_code": 0}
        apply_preview_projection(result, directory=self.root)
        self.assertEqual(result["preview"]["status"], "written")
        self.assertEqual(result["preview"]["source"], "legacy_result")
        self.assertEqual(result["preview_file"], str(self.image))

    def test_unattempted_preview_is_not_reported_as_a_failure(self):
        result = {"success": False, "preview_code": -1}
        block = normalize_preview(result, directory=self.root)
        self.assertEqual(block["status"], "not_attempted")

    def test_failed_code_on_a_saved_job_stays_failed(self):
        result = {"success": True, "preview_code": -3}
        self.assertEqual(normalize_preview(result, directory=self.root)["status"], "failed")

    def test_no_preview_evidence_projects_nothing(self):
        result = {"success": True}
        self.assertIsNone(normalize_preview(result, directory=self.root))
        apply_preview_projection(result, directory=self.root)
        self.assertNotIn("preview_status", result)
        self.assertNotIn("preview", result)

    def test_projection_keeps_the_save_outcome_untouched(self):
        result = {
            "success": True,
            "saved_file_reloaded_and_verified": True,
            "sha256": "a" * 64,
            "revision": 7,
            "preview_code": -5,
            "preview": self.native_block("failed", -5),
        }
        before = copy.deepcopy(result)
        apply_preview_projection(result, directory=self.root)
        for key in ("success", "saved_file_reloaded_and_verified", "sha256", "revision"):
            with self.subTest(key=key):
                self.assertEqual(result[key], before[key])

    def test_export_operation_keeps_one_result_with_preview_codes(self):
        result = {
            "success": True,
            "preview_code": 0,
            "preview": self.native_block(),
            "operations": [
                {
                    "op": "export",
                    "index": 0,
                    "label": "",
                    "succeeded": True,
                    "execution_status": "succeeded",
                    "effect_status": "committed",
                    "file": str(self.image),
                    "preview_code": 0,
                    "preview": self.native_block(),
                }
            ],
        }
        apply_preview_projection(result, directory=self.root)
        self.assertEqual(len(result["operations"]), 1)
        compact = bridge.compact_job({"status": "succeeded", "kind": "generic", "result": result})
        self.assertEqual(len(compact["result"]["operations"]), 1)
        self.assertEqual(compact["result"]["operations"][0]["preview_code"], 0)
        self.assertEqual(compact["result"]["preview_status"], "written")
        self.assertEqual(compact["result"]["preview"]["codes"]["raster"], 0)


class PreviewFileConfirmation(unittest.TestCase):
    """BUG-088: the raster stage and the filesystem stage stay distinguishable.

    Every fixture is isolated: a private temporary directory, no Creo, no job.
    A zero raster code is never enough on its own to report written.
    """

    def setUp(self):
        temporary = tempfile.TemporaryDirectory(prefix="t08a_preview_")
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        (self.root / "output").mkdir()
        self.image = self.root / "output" / "preview.jpg"

    def native(self, **overrides) -> dict:
        block = {
            "status": "written",
            "path": str(self.image),
            "bytes": 16,
            "codes": {"display": 0, "refit": 0, "repaint": 0, "raster": 0},
            "failed_step": None,
            "failed_code": None,
            "file_check": {
                "stage": "after_raster",
                "absolute": True,
                "parent_exists": True,
                "exists": True,
                "is_file": True,
                "size": 16,
                "error_code": 0,
                "error_category": None,
                "error_message": None,
            },
        }
        block.update(overrides)
        return block

    def test_raster_failure_never_reports_a_file_check(self):
        # Stage 1 fails: there is no file to confirm, so the block stays null.
        result = {
            "success": True,
            "preview_code": -5,
            "preview": self.native(
                status="failed",
                bytes=-1,
                failed_step="raster",
                failed_code=-5,
                file_check=None,
                codes={"display": 0, "refit": 0, "repaint": 0, "raster": -5},
            ),
        }
        block = normalize_preview(result, directory=self.root)
        self.assertEqual(block["status"], "failed")
        self.assertEqual(block["failed_step"], "raster")
        self.assertEqual(block["failed_code"], -5)
        self.assertIsNone(block["file_check"])

    def test_missing_file_after_a_zero_raster_code_keeps_the_real_error(self):
        check = {
            "stage": "after_raster",
            "absolute": True,
            "parent_exists": True,
            "exists": False,
            "is_file": False,
            "size": -1,
            "error_code": 2,
            "error_category": "system",
            "error_message": "The system cannot find the file specified.",
        }
        preview = self.native(
            status="failed", bytes=-1, failed_step="output_file", failed_code=-4, file_check=check
        )
        block = normalize_preview({"success": True, "preview": preview}, directory=self.root)
        self.assertEqual(block["status"], "failed")
        self.assertEqual(block["failed_step"], "output_file")
        self.assertEqual(block["failed_code"], -4)
        self.assertEqual(block["file_check"]["error_code"], 2)
        self.assertEqual(block["file_check"]["error_category"], "system")
        self.assertFalse(block["file_check"]["exists"])
        self.assertEqual(block["verification_error"], "FileNotFoundError")

    def test_empty_file_is_failed_even_though_the_path_exists(self):
        self.image.write_bytes(b"")
        preview = self.native(bytes=0, failed_step="output_file", failed_code=-1)
        block = normalize_preview({"success": True, "preview": preview}, directory=self.root)
        self.assertEqual(block["status"], "failed")
        self.assertEqual(block["bytes"], 0)
        # The native size claim is preserved; it is not rewritten by the probe.
        self.assertEqual(block["file_check"]["size"], 16)
        self.assertFalse(block["file_verified"])
        self.assertIsNone(block["verification_error"])

    def test_a_failed_stat_is_reported_without_an_invented_code(self):
        check = self.native()["file_check"] | {
            "exists": False,
            "size": -1,
            "error_code": 5,
            "error_category": "system",
            "error_message": "Access is denied.",
        }
        preview = self.native(file_check=check)
        with patch.object(Path, "stat", side_effect=PermissionError(13, "Access is denied")):
            block = normalize_preview({"success": True, "preview": preview}, directory=self.root)
        # The native says written but the file cannot be confirmed: the
        # projection downgrades it and reports the probe failure instead of a
        # code borrowed from the raster call.
        self.assertEqual(block["status"], "failed")
        self.assertEqual(block["failed_step"], "output_file_verification")
        self.assertIsNone(block["failed_code"])
        self.assertEqual(block["file_check"]["error_code"], 5)
        self.assertEqual(block["verification_error"], "PermissionError")

    def test_a_confirmed_file_stays_written_and_keeps_the_probe(self):
        self.image.write_bytes(b"confirmed preview bytes")
        preview = self.native()
        block = normalize_preview(
            {"success": True, "preview_code": 0, "preview": preview}, directory=self.root
        )
        self.assertEqual(block["status"], "written")
        self.assertTrue(block["file_verified"])
        self.assertEqual(block["file_check"]["stage"], "after_raster")
        self.assertIsNone(block["verification_error"])


class JobLevelDecoupling(unittest.TestCase):
    """A failed capture beside a verified save keeps the job succeeded."""

    def setUp(self):
        temporary = tempfile.TemporaryDirectory(prefix="t07_job_")
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
        self.part = path / "output" / "disk.prt.1"
        self.part.write_bytes(b"native part bytes")
        model = {
            "model_id": self.model_id,
            "model_name": "disk",
            "revision": 3,
            "status": "ready",
            "model_type": "part",
            "aliases": {},
            "inspection": {"features": [], "bodies": [{"id": 1}]},
            "part_file": str(self.part),
            "output_directory": str(path / "output"),
        }
        model_registry.write_model(path, model)
        self.job_id = "e" * 32
        directory = bridge.job_path(self.job_id)
        (directory / "output").mkdir(parents=True)
        self.directory = directory
        self.request = {
            "new": False,
            "model": {
                key: model[key] for key in ("model_id", "model_name", "model_type", "revision")
            },
            "operations": [{"op": "regenerate"}],
            "readonly": False,
        }
        bridge.write_json(directory / "request.json", self.request)
        self.manifest = {
            "job_id": self.job_id,
            "kind": "generic",
            "model_id": self.model_id,
            "status": "queued",
        }
        bridge.write_json(directory / "job.json", self.manifest)

    def run_worker(self, result: dict) -> dict:
        def fake_run(*args, **kwargs):
            bridge.write_json(self.directory / "native_result.json", result)
            return subprocess.CompletedProcess([], 0)

        with (
            patch.object(bridge.subprocess, "run", side_effect=fake_run),
            patch.object(bridge, "native_environment", return_value={}),
            patch.object(bridge, "note_native_outcome", return_value=None),
            patch.object(bridge, "config", return_value={}),
        ):
            general.run_generic_job(self.job_id, copy.deepcopy(self.manifest))
        return bridge.read_json(self.directory / "job.json")

    def plan_result(self, preview: dict, preview_code: int) -> dict:
        return {
            "success": True,
            "delivery_complete": True,
            "disconnect_code": 0,
            "saved_file_reloaded_and_verified": True,
            "part_file": str(self.part),
            "inspection": {"features": [], "bodies": [{"id": 1}]},
            "preview_code": preview_code,
            "preview": preview,
            "operations": [
                {
                    "op": "regenerate",
                    "index": 0,
                    "label": "",
                    "succeeded": True,
                    "execution_status": "succeeded",
                    "effect_status": "committed",
                }
            ],
        }

    def failed_preview(self) -> dict:
        return {
            "status": "failed",
            "path": str(self.directory / "output" / "preview.jpg"),
            "bytes": 0,
            "window": -1,
            "window_matches_model": False,
            "current_window_matches": False,
            "view_matrix_matches": False,
            "codes": {"display": 0, "window_get": -4, "refit": 0, "repaint": 0, "raster": -5},
            "failed_step": "raster",
            "failed_code": -5,
        }

    def test_preview_failure_does_not_fail_the_saved_job(self):
        manifest = self.run_worker(self.plan_result(self.failed_preview(), -5))
        self.assertEqual(manifest["status"], "succeeded")
        self.assertEqual(manifest["revision"], 4)
        self.assertTrue(manifest["result"]["saved_file_reloaded_and_verified"])
        self.assertEqual(manifest["result"]["preview_status"], "failed")
        self.assertIsNone(manifest["result"]["preview_file"])
        self.assertEqual(manifest["result"]["preview"]["codes"]["raster"], -5)
        self.assertEqual(manifest["result"]["preview"]["codes"]["window_get"], -4)
        self.assertEqual(manifest["result"]["operations"][0]["effect_status"], "committed")

    def test_written_preview_is_reported_beside_the_saved_model(self):
        image = self.directory / "output" / "preview.jpg"
        image.write_bytes(b"\xff\xd8\xff real capture")
        preview = self.failed_preview()
        preview.update(
            status="written", failed_step=None, failed_code=None, bytes=len(image.read_bytes())
        )
        manifest = self.run_worker(self.plan_result(preview, 0))
        self.assertEqual(manifest["status"], "succeeded")
        self.assertEqual(manifest["result"]["preview_status"], "written")
        self.assertEqual(manifest["result"]["preview_file"], str(image))
        compact = bridge.compact_job(manifest)
        self.assertEqual(compact["result"]["preview"]["status"], "written")

    def test_save_failure_is_not_masked_by_a_failed_preview(self):
        image = self.directory / "output" / "preview.jpg"
        image.write_bytes(b"\xff\xd8\xff stale capture")
        result = self.plan_result(self.failed_preview(), -5)
        result.update(success=False, saved_file_reloaded_and_verified=False, message="save failed")
        result.pop("inspection", None)
        manifest = self.run_worker(result)
        self.assertEqual(manifest["status"], "failed")
        self.assertEqual(manifest["result"]["preview_status"], "failed")
        self.assertIn("save failed", manifest["message"])


class DriverCoverage(unittest.TestCase):
    """BUG-088/BUG-066: the empty part, the solid body and the sheetmetal wall.

    The driver must be able to record the empty-part capture without turning a
    failed image into a driver error, and it must never overwrite an earlier
    report or image directory.
    """

    def setUp(self):
        temporary = tempfile.TemporaryDirectory(prefix="t07_driver_")
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)

    def acceptance(self) -> driver.Acceptance:
        return driver.Acceptance(
            client=None, output=self.root / "report.json", images=self.root / "images", run_id="r1"
        )

    def terminal(self, preview: dict) -> dict:
        return {
            "job_id": "j" * 32,
            "model_id": "m" * 32,
            "status": "succeeded",
            "revision": 1,
            "result": {"preview": preview, "preview_code": preview.get("codes", {}).get("raster")},
        }

    def failed_preview(self) -> dict:
        # The exact shape the 0.8.x feedback reports for the empty new part.
        return {
            "status": "failed",
            "path": str(self.root / "output" / "preview.jpg"),
            "bytes": -1,
            "file_verified": False,
            "codes": {
                "display": 0,
                "window_get": 0,
                "window_model_get": 0,
                "current_set": 0,
                "current_get": 0,
                "activate": 0,
                "view_matrix_set": 0,
                "view_matrix_get": 0,
                "refit": 0,
                "refresh": 0,
                "repaint": 0,
                "raster": 0,
            },
            "failed_step": "output_file",
            "failed_code": -4,
            "file_check": {
                "stage": "after_raster",
                "absolute": True,
                "parent_exists": True,
                "exists": False,
                "is_file": False,
                "size": -1,
                "error_code": 2,
                "error_category": "system",
                "error_message": "The system cannot find the file specified.",
            },
            "verification_error": "FileNotFoundError",
        }

    def written_preview(self) -> dict:
        image = self.root / "output" / "preview.jpg"
        image.parent.mkdir(parents=True, exist_ok=True)
        image.write_bytes(b"\xff\xd8\xff real capture bytes")
        return {
            "status": "written",
            "path": str(image),
            "bytes": image.stat().st_size,
            "file_verified": True,
            "codes": {
                "display": 0,
                "window_get": 0,
                "window_model_get": 0,
                "current_set": 0,
                "current_get": 0,
                "activate": 0,
                "view_matrix_set": 0,
                "view_matrix_get": 0,
                "refit": 0,
                "refresh": 0,
                "repaint": 0,
                "raster": 0,
            },
            "failed_step": None,
            "failed_code": None,
            "file_check": {
                "stage": "after_raster",
                "absolute": True,
                "parent_exists": True,
                "exists": True,
                "is_file": True,
                "size": image.stat().st_size,
                "error_code": 0,
                "error_category": None,
                "error_message": None,
            },
            "verification_error": None,
        }

    def test_the_empty_part_failure_is_recorded_not_raised(self):
        record = self.acceptance().check_preview(
            "empty_part", self.terminal(self.failed_preview()), expect_written=False
        )
        self.assertEqual(record["status"], "failed")
        self.assertEqual(record["failed_step"], "output_file")
        self.assertEqual(record["failed_code"], -4)
        self.assertIsNone(record["image"])
        # The filesystem evidence survives so the reviewer can tell a missing
        # file apart from a failed raster call.
        self.assertEqual(record["file_check"]["error_code"], 2)
        self.assertEqual(record["verification_error"], "FileNotFoundError")

    def test_the_empty_part_skip_is_recorded_without_an_image(self):
        preview = self.failed_preview()
        preview.update(
            status="skipped_no_geometry",
            failed_step=None,
            failed_code=None,
            file_check=None,
            verification_error=None,
        )
        preview["codes"] = {key: None for key in preview["codes"]}
        record = self.acceptance().check_preview(
            "empty_part", self.terminal(preview), expect_written=False
        )
        self.assertEqual(record["status"], "skipped_no_geometry")
        self.assertIsNone(record["image"])
        self.assertIsNone(record["failed_step"])

    def test_a_missing_image_is_never_reported_as_a_capture(self):
        # The same failed block must still be refused by the strict path: an
        # empty part cannot be counted as a written image.
        with self.assertRaises(AssertionError):
            self.acceptance().check_preview(
                "empty_part", self.terminal(self.failed_preview()), expect_written=True
            )

    def test_the_solid_body_capture_is_kept_for_human_review(self):
        record = self.acceptance().check_preview(
            "empty_part_solid", self.terminal(self.written_preview())
        )
        self.assertEqual(record["status"], "written")
        self.assertIsNotNone(record["image"])
        self.assertGreater(record["image"]["bytes"], 0)
        self.assertEqual(record["image"]["content_verification"], "human_review_pending")

    def test_the_empty_plan_models_nothing(self):
        self.assertEqual(driver.empty_plan(), [])

    def test_the_sheetmetal_fixture_is_one_flat_wall(self):
        from creo_mechdog.schema import validate_operations

        operations = validate_operations(driver.sheetmetal_plan())
        self.assertEqual([op["op"] for op in operations], ["sketch", "sheetmetal_wall"])
        wall = operations[1]
        self.assertEqual(wall["plane"] if "plane" in wall else operations[0]["plane"], "XZ")
        self.assertEqual(wall["depth"], driver.WALL_DEPTH_MM)
        self.assertEqual(wall["thickness"], driver.WALL_THICKNESS_MM)
        self.assertEqual(
            driver.sheetmetal_volume(),
            driver.WALL_LENGTH_MM * driver.WALL_THICKNESS_MM * driver.WALL_DEPTH_MM,
        )

    def test_a_new_run_id_is_unique(self):
        self.assertNotEqual(driver.new_run_id(), driver.new_run_id())

    def test_an_existing_report_is_never_overwritten(self):
        existing = self.root / "report.json"
        existing.write_text("{}", encoding="utf-8")
        with self.assertRaises(ValueError):
            driver.resolve_output(existing, "r1")

    def test_a_new_report_gets_its_own_directory(self):
        output = driver.resolve_output(None, "run-1")
        self.assertIn("run-1", str(output))
        self.assertFalse(output.exists())
        images = driver.resolve_images(None, "run-1")
        self.assertIn("run-1", str(images))
        self.assertNotEqual(str(images), str(output))

    def test_the_images_directory_follows_the_report(self):
        output = self.root / "run-2" / "report.json"
        images = driver.resolve_images(output, "run-2")
        self.assertEqual(images, self.root / "run-2" / "images")


class FakeToolResult:
    def __init__(self, structured: dict) -> None:
        self.is_error = False
        self.structured_content = structured
        self.content = "ok"


class FakeClient:
    """A scripted MCP client: every call is recorded, nothing is connected."""

    def __init__(self, image: Path) -> None:
        self.calls: list[tuple[str, dict]] = []
        self.image = image

    async def call_tool(self, name: str, args: dict):
        self.calls.append((name, args))
        if name == "creo_new_sheetmetal":
            return FakeToolResult({"job_id": "j" * 32, "model_id": "m" * 32, "revision": 0})
        if name == "creo_execute_plan":
            return FakeToolResult({"job_id": "k" * 32})
        if name == "creo_get_job":
            job_id = args["job_id"]
            revision = 1 if job_id == "j" * 32 else 2
            return FakeToolResult(
                {
                    "job_id": job_id,
                    "model_id": "m" * 32,
                    "status": "succeeded",
                    "revision": revision,
                    "result": {
                        "preview": {
                            "status": "written",
                            "codes": {
                                "display": 0,
                                "window_get": 0,
                                "window_model_get": 0,
                                "current_set": 0,
                                "current_get": 0,
                                "activate": 0,
                                "view_matrix_set": 0,
                                "view_matrix_get": 0,
                                "refit": 0,
                                "refresh": 0,
                                "repaint": 0,
                                "raster": 0,
                            },
                            "failed_step": None,
                            "failed_code": None,
                            "file_verified": True,
                            "path": str(self.image),
                        },
                        "preview_code": 0,
                    },
                }
            )
        raise AssertionError(f"unexpected tool {name}")


class SheetmetalFixture(unittest.TestCase):
    """N11: the wall plan must run on a sheetmetal model, not on a part.

    A sheetmetal operation is refused on a part model ("Sheetmetal operations
    require an MCP sheetmetal model"), so the fixture creates the comparison
    model with the sheetmetal entry point and continues that model.
    """

    def setUp(self):
        temporary = tempfile.TemporaryDirectory(prefix="t07_sheetmetal_")
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        (self.root / "output").mkdir()
        self.image = self.root / "output" / "preview.jpg"
        self.image.write_bytes(b"\xff\xd8\xff sheetmetal capture bytes")
        self.client = FakeClient(self.image)
        self.acceptance = driver.Acceptance(
            client=self.client,
            output=self.root / "report.json",
            images=self.root / "images",
            run_id="20261031T120000_ab12cd34",
        )

    def test_the_model_name_is_unique_and_fits_the_label_rule(self):
        name = driver.sheetmetal_model_name("20261031T120000_ab12cd34")
        self.assertRegex(name, r"^[a-z0-9][a-z0-9_]{0,30}$")
        self.assertLessEqual(len(name), 31)
        self.assertNotEqual(name, driver.sheetmetal_model_name("20261031T130000_ff00ff00"))

    def test_the_wall_plan_continues_the_sheetmetal_model(self):
        import asyncio

        created = asyncio.run(self.acceptance.sheetmetal_part_case("t07_sheetmetal_ab12cd34"))
        self.assertEqual(created["status"], "succeeded")
        self.assertEqual(created["model_id"], "m" * 32)
        # The creation job takes the new model from revision 0 to 1, so the
        # wall plan continues it with that revision.
        self.assertEqual(created["revision"], 1)

        terminal = asyncio.run(
            self.acceptance.plan(driver.sheetmetal_plan(), created["model_id"], created["revision"])
        )
        self.assertEqual(terminal["status"], "succeeded")

        names = [name for name, _ in self.client.calls]
        self.assertEqual(names[0], "creo_new_sheetmetal")
        self.assertIn("creo_execute_plan", names)
        plan_call = next(args for name, args in self.client.calls if name == "creo_execute_plan")
        self.assertEqual(plan_call["model_id"], "m" * 32)
        self.assertEqual(plan_call["expected_revision"], 1)
        # The wall plan is submitted against the sheetmetal model; it is never
        # submitted as a new model, which would create a part.
        self.assertNotIn("model_type", plan_call)
        self.assertEqual(
            [op["op"] for op in plan_call["operations"]], ["sketch", "sheetmetal_wall"]
        )

    def test_a_failed_sheetmetal_model_creation_is_not_continued(self):
        import asyncio

        class Failing(FakeClient):
            async def call_tool(self, name: str, args: dict):
                if name == "creo_get_job":
                    self.calls.append((name, args))
                    return FakeToolResult(
                        {
                            "job_id": args["job_id"],
                            "model_id": "m" * 32,
                            "status": "failed",
                            "revision": None,
                            "message": "template missing",
                        }
                    )
                return await super().call_tool(name, args)

        client = Failing(self.image)
        acceptance = driver.Acceptance(
            client=client,
            output=self.root / "failed.json",
            images=self.root / "images",
            run_id="20261031T120000_ab12cd34",
        )
        with self.assertRaises(RuntimeError):
            asyncio.run(acceptance.sheetmetal_part_case("t07_sheetmetal_ab12cd34"))
        # No wall plan may be submitted after a failed creation.
        self.assertNotIn("creo_execute_plan", [name for name, _ in client.calls])


class DatumDisplayGuardNative(unittest.TestCase):
    """FEAT-008/BUG-088 (H): hide for an assembly capture, restore always.

    Structural guards over native/preview.h: the previous display state is
    read before anything is hidden, the restore runs on every exit path of the
    capture (failed steps included), and the user's config.pro is never
    written - only session display options are touched and put back.
    """

    def setUp(self):
        self.shared = native_source("preview.h")

    def hide_block(self) -> str:
        return region(self.shared, "void hide(ProMdl model)", "void restore()")

    def restore_block(self) -> str:
        return region(self.shared, "void restore()", "// Filesystem confirmation")

    def test_the_previous_value_is_read_before_anything_is_hidden(self):
        hide = self.hide_block()
        self.assertIn("ProConfigoptionGet", hide)
        self.assertLess(hide.index("ProConfigoptionGet"), hide.index("ProConfigoptSet"))
        self.assertIn("previous_known = true", hide)
        # An option whose previous value cannot be read is never hidden.
        self.assertIn("never hidden", hide)
        restore = self.restore_block()
        self.assertIn("ProConfigoptSet", restore)
        self.assertIn("previous_value.c_str()", restore)

    def test_only_an_assembly_capture_hides_datums(self):
        hide = self.hide_block()
        self.assertIn("ProMdlTypeGet", hide)
        self.assertIn("model_type != PRO_ASSEMBLY", hide)
        self.assertIn('"not_applicable"', hide)
        for name in (
            "DATUM_DISPLAY",
            "AXIS_DISPLAY",
            "DATUM_POINT_DISPLAY",
            "DISPLAY_COORDINATE_SYS",
        ):
            with self.subTest(option=name):
                self.assertIn(name, self.shared)

    def test_the_restore_runs_on_every_exit_path(self):
        # The guard is constructed by the step body and writes its evidence
        # into the outcome by reference, so bare `return;` statements cannot
        # skip the restore: the destructor is the safety net.
        destructor = region(self.shared, "~PreviewDatumDisplayGuard()", "void hide(ProMdl model)")
        self.assertIn("restore();", destructor)
        steps = region(self.shared, "static void capture_preview_steps", "// One capture attempt.")
        self.assertIn("PreviewStepOutcome &outcome", steps)
        self.assertIn("PreviewDatumDisplayGuard datums(outcome)", steps)
        self.assertLess(steps.index("datums.hide(model)"), steps.index("ProRasterFileWrite"))
        self.assertNotIn("return outcome", steps)
        restore = self.restore_block()
        self.assertIn("datum_restore_status = restored_count == hidden_count", restore)
        self.assertIn('"restored"', restore)

    def test_the_user_config_file_is_never_written(self):
        # No config-file write API and no config.pro path literal: only the
        # session display options are read, changed and put back.
        for token in ("ProConfigStore", "ProFileEdit", "ProConfigfileWrite", '"config.pro"'):
            with self.subTest(token=token):
                self.assertNotIn(token, self.shared)
        self.assertIn("ProConfigoptSet", self.shared)
        self.assertIn("ProConfigoptionGet", self.shared)

    def test_the_occlusion_evidence_is_published_in_its_own_block(self):
        block = region(self.shared, '"datum_display"', '"config_file_written", false')
        for key in (
            '"model_type"',
            '"applicable"',
            '"attempted"',
            '"hide_status"',
            '"restore_status"',
            '"options"',
        ):
            with self.subTest(key=key):
                self.assertIn(key, block)
        # The block is a sibling of the capture codes, not a rewrite of them.
        self.assertIn('{"datum_display",', compact(self.shared))

    def test_the_capture_status_never_reads_the_datum_fields(self):
        written = region(self.shared, "static bool preview_written", "// Result/diagnostic block.")
        self.assertNotIn("datum", written)
        self.assertIn(
            compact('preview_written(outcome) ? "written" : "failed"'), compact(self.shared)
        )


class OcclusionProjection(unittest.TestCase):
    """The projection passes the block through and leaves the status alone."""

    def setUp(self):
        temporary = tempfile.TemporaryDirectory(prefix="t07_datums_")
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        (self.root / "output").mkdir()
        self.image = self.root / "output" / "preview.jpg"
        self.image.write_bytes(b"\xff\xd8\xff assembly capture")

    def native(self, **overrides) -> dict:
        block = {
            "status": "written",
            "path": str(self.image),
            "bytes": 20,
            "codes": {"display": 0, "refit": 0, "repaint": 0, "raster": 0},
            "failed_step": None,
            "failed_code": None,
            "datum_display": {
                "model_type": "assembly",
                "type_query_code": 0,
                "applicable": True,
                "attempted": True,
                "hide_status": "hidden",
                "restore_status": "restored",
                "options": [
                    {
                        "name": "DATUM_DISPLAY",
                        "get_code": 0,
                        "hide_code": 0,
                        "restore_code": 0,
                        "previous_value": "yes",
                        "hidden": True,
                        "restored": True,
                    }
                ],
                "config_file_written": False,
            },
        }
        block.update(overrides)
        return block

    def test_the_block_passes_through_without_touching_the_status(self):
        result = {"success": True, "preview": self.native()}
        block = normalize_preview(result, directory=self.root)
        self.assertEqual(block["status"], "written")
        self.assertEqual(block["datum_display"]["hide_status"], "hidden")
        self.assertEqual(block["datum_display"]["restore_status"], "restored")
        self.assertFalse(block["datum_display"]["config_file_written"])
        self.assertEqual(block["datum_display"]["options"][0]["previous_value"], "yes")

    def test_the_status_survives_every_occlusion_outcome(self):
        for status in ("written", "failed", "not_attempted"):
            for datums in (
                self.native()["datum_display"],
                {
                    "model_type": "assembly",
                    "applicable": True,
                    "attempted": True,
                    "hide_status": "partial",
                    "restore_status": "restored",
                    "options": [],
                    "config_file_written": False,
                },
                {
                    "model_type": "assembly",
                    "applicable": True,
                    "attempted": True,
                    "hide_status": "failed",
                    "restore_status": "not_attempted",
                    "options": [],
                    "config_file_written": False,
                },
                None,
            ):
                with self.subTest(status=status, datums=datums is not None):
                    preview = self.native(status=status, datum_display=datums)
                    if status != "written":
                        preview.update(failed_step="raster", failed_code=-5)
                    block = normalize_preview(
                        {"success": status != "not_attempted", "preview": preview},
                        directory=self.root,
                    )
                    self.assertEqual(block["datum_display"], datums)
                    if status == "written":
                        self.assertEqual(block["status"], "written")
                    else:
                        self.assertNotEqual(block["status"], "written")

    def test_results_without_the_block_keep_the_plain_shape(self):
        result = {
            "success": True,
            "preview": {
                "status": "written",
                "path": str(self.image),
                "codes": {"raster": 0},
                "datum_display": None,
            },
        }
        block = normalize_preview(result, directory=self.root)
        self.assertIsNone(block["datum_display"])
        self.assertEqual(block["status"], "written")


class DriverDatumCoverage(unittest.TestCase):
    """The driver records the occlusion evidence and enforces the contract."""

    def test_the_assembly_plan_is_valid_and_labels_are_legal(self):
        from creo_mechdog.schema import validate_operations

        operations = validate_operations(driver.assembly_plan("a" * 32))
        self.assertEqual(
            [op["op"] for op in operations],
            ["datum_axis", "assemble_component", "assemble_component"],
        )
        self.assertEqual(operations[1]["label"], "plate_a")
        self.assertEqual(operations[2]["translation"], [100, 0, 0])
        self.assertEqual(operations[1]["source_model_id"], "a" * 32)
        self.assertEqual(operations[1]["placement"], "fixed")

    def test_assembly_model_names_are_legal_and_unique(self):
        name = driver.assembly_model_name("20261101T120000_ab12cd34")
        self.assertRegex(name, r"^[a-z0-9][a-z0-9_]{0,30}$")
        self.assertLessEqual(len(name), 31)
        self.assertNotEqual(name, driver.assembly_model_name("20261101T130000_ff00ff00"))

    def datum_block(self, **overrides) -> dict:
        block = {
            "model_type": "assembly",
            "type_query_code": 0,
            "applicable": True,
            "attempted": True,
            "hide_status": "hidden",
            "restore_status": "restored",
            "options": [],
            "config_file_written": False,
        }
        block.update(overrides)
        return block

    def acceptance(self, root: Path) -> driver.Acceptance:
        return driver.Acceptance(
            client=None, output=root / "report.json", images=root / "images", run_id="r1"
        )

    def terminal(self, datum_display: dict | None) -> dict:
        image = self.image if hasattr(self, "image") else None
        return {
            "job_id": "j" * 32,
            "model_id": "m" * 32,
            "status": "succeeded",
            "revision": 2,
            "result": {
                "preview_code": 0,
                "preview": {
                    "status": "written",
                    "path": str(image) if image else "x.jpg",
                    "codes": {
                        "display": 0,
                        "window_get": 0,
                        "window_model_get": 0,
                        "current_set": 0,
                        "current_get": 0,
                        "activate": 0,
                        "view_matrix_set": 0,
                        "view_matrix_get": 0,
                        "refit": 0,
                        "refresh": 0,
                        "repaint": 0,
                        "raster": 0,
                    },
                    "failed_step": None,
                    "failed_code": None,
                    "file_verified": True,
                    "datum_display": datum_display,
                },
            },
        }

    def test_the_driver_records_the_block_and_requires_the_restore(self):
        temporary = tempfile.TemporaryDirectory(prefix="t07_asm_")
        self.addCleanup(temporary.cleanup)
        root = Path(temporary.name)
        (root / "output").mkdir()
        self.image = root / "output" / "preview.jpg"
        self.image.write_bytes(b"\xff\xd8\xff assembly capture bytes")
        acceptance = self.acceptance(root)
        record = acceptance.check_preview(
            "assembly_components",
            self.terminal(self.datum_block()),
            expect_datums=True,
        )
        self.assertEqual(record["datum_display"]["hide_status"], "hidden")
        self.assertEqual(record["datum_display"]["restore_status"], "restored")

    def test_a_hidden_display_must_be_restored(self):
        temporary = tempfile.TemporaryDirectory(prefix="t07_asm_")
        self.addCleanup(temporary.cleanup)
        root = Path(temporary.name)
        (root / "output").mkdir()
        self.image = root / "output" / "preview.jpg"
        self.image.write_bytes(b"\xff\xd8\xff assembly capture bytes")
        acceptance = self.acceptance(root)
        with self.assertRaises(AssertionError):
            acceptance.check_preview(
                "assembly_components",
                self.terminal(self.datum_block(hide_status="hidden", restore_status="failed")),
                expect_datums=True,
            )

    def test_the_assembly_case_needs_applicable_and_attempted(self):
        temporary = tempfile.TemporaryDirectory(prefix="t07_asm_")
        self.addCleanup(temporary.cleanup)
        root = Path(temporary.name)
        (root / "output").mkdir()
        self.image = root / "output" / "preview.jpg"
        self.image.write_bytes(b"\xff\xd8\xff assembly capture bytes")
        acceptance = self.acceptance(root)
        for block in (
            None,
            self.datum_block(applicable=False),
            self.datum_block(attempted=False),
            self.datum_block(hide_status="failed", restore_status="not_attempted"),
        ):
            with self.subTest(block=block):
                with self.assertRaises(AssertionError):
                    acceptance.check_preview(
                        "assembly_components",
                        self.terminal(block),
                        expect_datums=True,
                    )

    def test_other_cases_keep_recording_the_block_without_the_assembly_rule(self):
        temporary = tempfile.TemporaryDirectory(prefix="t07_asm_")
        self.addCleanup(temporary.cleanup)
        root = Path(temporary.name)
        (root / "output").mkdir()
        self.image = root / "output" / "preview.jpg"
        self.image.write_bytes(b"\xff\xd8\xff assembly capture bytes")
        acceptance = self.acceptance(root)
        # A part capture reports not_applicable and passes the usual checks.
        record = acceptance.check_preview(
            "disk",
            self.terminal(
                self.datum_block(
                    model_type="part",
                    applicable=False,
                    attempted=False,
                    hide_status="not_applicable",
                    restore_status="not_applicable",
                )
            ),
        )
        self.assertEqual(record["datum_display"]["model_type"], "part")
        self.assertEqual(record["status"], "written")


class AssemblyFixture(unittest.TestCase):
    """The assembly case drives the public entry points and records evidence.

    A scripted client stands in for the MCP server; nothing connects to Creo.
    """

    def setUp(self):
        temporary = tempfile.TemporaryDirectory(prefix="t07_asmfix_")
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        self.image = self.root / "output" / "preview.jpg"
        self.image.parent.mkdir(parents=True)
        self.image.write_bytes(b"\xff\xd8\xff assembly preview bytes")
        self.client = FakeAssemblyClient(self.image)
        self.acceptance = driver.Acceptance(
            client=self.client,
            output=self.root / "report.json",
            images=self.root / "images",
            run_id="20261101T120000_ab12cd34",
        )

    def test_the_assembly_case_uses_the_assembly_entry_point(self):
        import asyncio

        created = asyncio.run(self.acceptance.assembly_case())
        self.assertEqual(created["status"], "succeeded")
        self.assertEqual(created["model_id"], "m" * 32)
        names = [name for name, _ in self.client.calls]
        self.assertEqual(names[0], "creo_new_assembly")
        self.assertEqual(
            self.acceptance.report["assembly_model"]["created_with"], "creo_new_assembly"
        )

    def test_the_assembly_preview_carries_the_occlusion_evidence(self):
        import asyncio

        terminal = asyncio.run(self.acceptance.plan(driver.assembly_plan("a" * 32), "m" * 32, 1))
        record = self.acceptance.check_preview("assembly_components", terminal, expect_datums=True)
        self.assertEqual(record["datum_display"]["model_type"], "assembly")
        self.assertEqual(record["datum_display"]["restore_status"], "restored")
        self.assertFalse(record["datum_display"]["config_file_written"])


class FakeAssemblyClient(FakeClient):
    """FakeClient plus the assembly entry point and a datum_display receipt."""

    def datum_display(self) -> dict:
        return {
            "model_type": "assembly",
            "type_query_code": 0,
            "applicable": True,
            "attempted": True,
            "hide_status": "hidden",
            "restore_status": "restored",
            "options": [
                {
                    "name": "DATUM_DISPLAY",
                    "get_code": 0,
                    "hide_code": 0,
                    "restore_code": 0,
                    "previous_value": "yes",
                    "hidden": True,
                    "restored": True,
                }
            ],
            "config_file_written": False,
        }

    async def call_tool(self, name: str, args: dict):
        if name == "creo_new_assembly":
            self.calls.append((name, args))
            return FakeToolResult({"job_id": "j" * 32, "model_id": "m" * 32, "revision": 1})
        result = await super().call_tool(name, args)
        if name == "creo_get_job":
            preview = result.structured_content["result"]["preview"]
            preview["datum_display"] = self.datum_display()
        return result


if __name__ == "__main__":
    unittest.main()
