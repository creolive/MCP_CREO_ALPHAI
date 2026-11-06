"""BUG-113: offline diagnostics for a failed save and a failed rollback check.

Nothing here connects to Creo. The projection tests feed synthetic native
blocks; the native assertions read ``native/generic.cpp`` to lock the wiring.
The four offline classes are: a failed ``ProMdlnameBackup``, a checkpoint that
cannot be reloaded, a restored state whose feature count differs while the
volume matches, and a successful rollback whose semantics stay untouched.
"""

from __future__ import annotations

import unittest
from pathlib import Path

import bridge
import generic_bridge as general
from creo_mechdog import operation_results

ROOT = Path(__file__).resolve().parents[2]
NATIVE = ROOT / "native"
SAMPLE_LIMIT = operation_results.SAMPLE_LIMIT


def native_source() -> str:
    return (NATIVE / "generic.cpp").read_text(encoding="utf-8")


def region(source: str, start: str, stop: str) -> str:
    begin = source.index(start)
    return source[begin : source.index(stop, begin)]


def compact(source: str) -> str:
    """Whitespace-free view so markers survive clang-format line breaks."""
    return "".join(source.split())


def save_failure_block(**overrides) -> dict:
    block = {
        "call": "ProMdlnameBackup",
        "code": -1,
        "stage": "verify_model_save",
        "destination": "wb_srf.prt",
        "source_checkpoint": "wb_srf.prt.4",
        "candidate_files": {
            "available": True,
            "total": 1,
            "truncated": False,
            "sample": ["wb_srf.prt.4"],
        },
    }
    block.update(overrides)
    return block


def collection(before_ids: list[int], after_ids: list[int], **overrides) -> dict:
    missing = [feature_id for feature_id in before_ids if feature_id not in after_ids]
    added = [feature_id for feature_id in after_ids if feature_id not in before_ids]
    block = {
        "available": True,
        "before": len(before_ids),
        "after": len(after_ids),
        "missing_ids": {"total": len(missing), "truncated": False, "sample": missing},
        "added_ids": {"total": len(added), "truncated": False, "sample": added},
        "reason": None,
    }
    block.update(overrides)
    return block


def unavailable_collection(reason: str) -> dict:
    return {
        "available": False,
        "before": None,
        "after": None,
        "missing_ids": None,
        "added_ids": None,
        "reason": reason,
    }


def difference_block(**overrides) -> dict:
    block = {
        "available": True,
        "status": "mismatch",
        "reason": "Saved feature/body count changed",
        "features": collection([1, 2, 3], [1, 2, 3, 4]),
        "bodies": collection([10], [10]),
        "volume_mm3": {"available": True, "before": 1000.0, "after": 1000.0, "reason": None},
    }
    block.update(overrides)
    return block


def failed_result(**overrides) -> dict:
    result = {
        "success": False,
        "saved_file_reloaded_and_verified": False,
        "rollback_succeeded": False,
        "message": "Toolkit call ProMdlnameBackup(board, destination) failed with code -1 "
        "during verify_model_save",
        "toolkit_code": -1,
        "operations": [
            {
                "op": "trim",
                "index": 0,
                "label": "trim_srf",
                "succeeded": False,
                "execution_status": "failed",
            }
        ],
    }
    result.update(overrides)
    return result


class SaveFailureReceiptTests(unittest.TestCase):
    def test_native_records_the_failed_backup_before_the_throw(self):
        generic = native_source()
        body = region(
            generic,
            'generic_substage("verify_model_save");',
            "saved = latest_model_file();",
        )
        self.assertIn("ProError backup = ProMdlnameBackup(board, destination);", body)
        self.assertLess(body.index('report["save_failure"]'), body.index("check(backup,"))
        # The failure text stays the CK form callers already match on.
        self.assertIn('check(backup, "ProMdlnameBackup(board, destination)");', body)

    def test_native_block_carries_the_fixed_keys_and_stays_bounded(self):
        generic = native_source()
        body = region(generic, "static J save_failure_report(", "static bool collect_ids(")
        for expected in (
            '"call", "ProMdlnameBackup"',
            '"code", code',
            '"stage", stage',
            '"destination"',
            '"source_checkpoint"',
            '"candidate_files"',
        ):
            self.assertIn(expected, body)
        self.assertIn("managed_relative_name(checkpoint, directory)", body)
        bounded = region(
            generic, "static J bounded_ids(", "static J rollback_collection_difference("
        )
        self.assertIn("RECOVERY_SAMPLE_LIMIT", bounded)

    def test_projection_keeps_the_raw_code_call_and_stage(self):
        normalized = operation_results.normalize_save_failure(save_failure_block())
        self.assertEqual(normalized["call"], "ProMdlnameBackup")
        self.assertEqual(normalized["code"], -1)
        self.assertEqual(normalized["stage"], "verify_model_save")
        self.assertEqual(normalized["destination"], "wb_srf.prt")
        self.assertEqual(normalized["source_checkpoint"], "wb_srf.prt.4")

    def test_candidate_files_are_capped_with_totals_kept(self):
        names = [f"wb_srf.prt.{index}" for index in range(25)]
        block = save_failure_block(
            candidate_files={"available": True, "total": 25, "truncated": True, "sample": names}
        )
        normalized = operation_results.normalize_save_failure(block)
        files = normalized["candidate_files"]
        self.assertEqual(len(files["sample"]), SAMPLE_LIMIT)
        self.assertEqual(files["total"], 25)
        self.assertTrue(files["truncated"])

    def test_new_block_does_not_override_the_failure_message(self):
        result = failed_result(save_failure=save_failure_block())
        annotated = operation_results.annotate_native_result(result, readonly=False)
        self.assertEqual(annotated["save_failure"]["code"], -1)
        self.assertIn("ProMdlnameBackup", annotated["message"])
        self.assertIn("code -1", annotated["message"])
        self.assertEqual(annotated["toolkit_code"], -1)
        self.assertFalse(annotated["rollback_succeeded"])

    def test_legacy_result_without_the_block_is_not_given_one(self):
        annotated = operation_results.annotate_native_result(failed_result(), readonly=False)
        self.assertNotIn("save_failure", annotated)
        self.assertNotIn("rollback_difference", annotated)


class RollbackLoadFailureTests(unittest.TestCase):
    def load_failure_block(self) -> dict:
        reason = "checkpoint reload failed with code -27"
        return {
            "available": False,
            "status": "unavailable",
            "reason": reason,
            "features": unavailable_collection("baseline inspection carries no features"),
            "bodies": unavailable_collection("baseline inspection carries no bodies"),
            "volume_mm3": {
                "available": False,
                "before": None,
                "after": None,
                "reason": "volume was not measured on both sides, so geometry cannot be compared",
            },
        }

    def test_native_load_failure_publishes_an_unavailable_difference(self):
        generic = native_source()
        body = region(generic, 'report["rollback_code"] = loaded;', "// BUG-096")
        self.assertIn('report["rollback_difference"]', body)
        self.assertIn("checkpoint reload failed with code", body)

    def test_projection_reports_unavailable_with_the_reason(self):
        normalized = operation_results.normalize_rollback_difference(self.load_failure_block())
        self.assertFalse(normalized["available"])
        self.assertEqual(normalized["status"], "unavailable")
        self.assertIn("code -27", normalized["reason"])
        self.assertFalse(normalized["features"]["available"])
        self.assertIsNone(normalized["features"]["missing_ids"])
        self.assertFalse(normalized["volume_mm3"]["available"])
        self.assertIsNone(normalized["volume_mm3"]["before"])

    def test_failed_load_keeps_the_existing_rollback_evidence(self):
        result = failed_result(
            rollback_code=-27,
            rollback_message="Restored file could not be regenerated and verified "
            "against its saved baseline",
            rollback_difference=self.load_failure_block(),
        )
        annotated = operation_results.annotate_native_result(result, readonly=False)
        self.assertFalse(annotated["rollback_succeeded"])
        self.assertEqual(annotated["rollback_code"], -27)
        self.assertEqual(
            annotated["rollback_message"],
            "Restored file could not be regenerated and verified against its saved baseline",
        )
        self.assertEqual(annotated["rollback_difference"]["status"], "unavailable")
        self.assertEqual(annotated["operations"][0]["effect_status"], "unknown")
        self.assertEqual(
            general.failed_model_status({}, annotated, {"part_file": "wb_srf.prt.4"}), "failed"
        )


class RollbackMismatchTests(unittest.TestCase):
    def test_count_difference_with_equal_volume_is_a_mismatch(self):
        block = difference_block(
            features=collection([1, 2, 3], [1, 2, 3, 4]),
            bodies=collection([10], [10]),
            volume_mm3={"available": True, "before": 1000.0, "after": 1000.0, "reason": None},
        )
        normalized = operation_results.normalize_rollback_difference(block)
        self.assertEqual(normalized["status"], "mismatch")
        self.assertEqual(normalized["features"]["before"], 3)
        self.assertEqual(normalized["features"]["after"], 4)
        self.assertEqual(normalized["features"]["missing_ids"]["total"], 0)
        self.assertEqual(normalized["features"]["added_ids"]["sample"], [4])
        self.assertEqual(normalized["volume_mm3"]["before"], 1000.0)
        self.assertEqual(normalized["volume_mm3"]["after"], 1000.0)

    def test_mismatch_does_not_make_the_model_ready_or_roll_back_effects(self):
        result = failed_result(
            rollback_message="Saved feature/body count changed",
            rollback_difference=difference_block(),
        )
        annotated = operation_results.annotate_native_result(result, readonly=False)
        self.assertFalse(annotated["rollback_succeeded"])
        self.assertEqual(annotated["rollback_difference"]["status"], "mismatch")
        self.assertEqual(annotated["operations"][0]["effect_status"], "unknown")
        self.assertEqual(
            general.failed_model_status({}, annotated, {"part_file": "wb_srf.prt.4"}), "failed"
        )

    def test_malformed_ids_degrade_to_unavailable_instead_of_a_verdict(self):
        block = difference_block(features=collection([1, 2, 3], [1, 2, 3], missing_ids="1,2"))
        normalized = operation_results.normalize_rollback_difference(block)
        self.assertEqual(normalized["status"], "unavailable")
        self.assertFalse(normalized["available"])
        self.assertIsNone(normalized["features"]["missing_ids"])
        self.assertIn("malformed", normalized["features"]["reason"])


class SuccessfulRollbackTests(unittest.TestCase):
    def matched_block(self) -> dict:
        return difference_block(
            status="matched",
            reason=None,
            features=collection([1, 2, 3], [1, 2, 3]),
            bodies=collection([10], [10]),
        )

    def test_matched_evidence_leaves_rollback_semantics_unchanged(self):
        result = failed_result(rollback_succeeded=True, rollback_difference=self.matched_block())
        annotated = operation_results.annotate_native_result(result, readonly=False)
        self.assertTrue(annotated["rollback_succeeded"])
        self.assertEqual(annotated["rollback_difference"]["status"], "matched")
        self.assertEqual(annotated["operations"][0]["effect_status"], "rolled_back")
        self.assertEqual(
            general.failed_model_status({}, annotated, {"part_file": "wb_srf.prt.4"}), "ready"
        )

    def test_native_sets_rollback_succeeded_only_after_verify_saved(self):
        generic = native_source()
        body = region(
            generic, "J rollback_baseline = nullptr;", 'report["rollback_code"] = loaded;'
        )
        self.assertLess(
            body.index("rollback_restored = restored;"),
            body.index("verify_saved(rollback_baseline, restored);"),
        )
        self.assertLess(
            body.index("verify_saved(rollback_baseline, restored);"),
            body.index('report["rollback_succeeded"] = true;'),
        )
        self.assertEqual(body.count('report["rollback_succeeded"]'), 1)

    def test_difference_report_never_decides_the_rollback(self):
        generic = native_source()
        body = region(
            generic,
            "static J rollback_difference_report(",
            "static void failed_placement_matrix(",
        )
        self.assertNotIn("rollback_succeeded", body)
        self.assertNotIn('verified"', body)


class CompactVisibilityTests(unittest.TestCase):
    def manifest(self) -> dict:
        return {
            "job_id": "a" * 32,
            "kind": "generic",
            "model_id": "c" * 32,
            "status": "failed",
            "stage": "verify_model_save",
            "revision": 4,
            "readonly": False,
            "created_at": "2026-11-06T00:00:00+00:00",
            "finished_at": "2026-11-06T00:01:00+00:00",
            "message": "failed",
            "operations": [{"op": "trim", "label": "trim_srf"}],
            "result": failed_result(
                rollback_message="Saved feature/body count changed",
                rollback_code=None,
                save_failure=save_failure_block(),
                rollback_difference=difference_block(),
                part_file=r"E:\models\c\output\wb_srf.prt.4",
                sha256="b" * 64,
            ),
        }

    def test_empty_sections_selection_keeps_both_failure_blocks(self):
        summary = bridge.compact_job(self.manifest(), sections=[])
        result = summary["result"]
        self.assertEqual(summary["sections_applied"], [])
        self.assertIn("save_failure", result)
        self.assertIn("rollback_difference", result)
        self.assertEqual(result["save_failure"]["code"], -1)
        self.assertEqual(result["rollback_difference"]["status"], "mismatch")
        self.assertIn("ProMdlnameBackup", result["message"])
        self.assertEqual(result["rollback_message"], "Saved feature/body count changed")
        self.assertNotIn("inspection", result)

    def test_unnamed_selection_still_carries_the_failure_evidence(self):
        summary = bridge.compact_job(self.manifest(), sections=["preview"])
        result = summary["result"]
        self.assertEqual(summary["sections_applied"], ["preview"])
        self.assertIn("save_failure", result)
        self.assertIn("rollback_difference", result)

    def test_compact_never_fabricates_the_blocks_for_legacy_results(self):
        manifest = self.manifest()
        manifest["result"] = failed_result()
        result = bridge.compact_job(manifest, sections=[])["result"]
        self.assertNotIn("save_failure", result)
        self.assertNotIn("rollback_difference", result)


if __name__ == "__main__":
    unittest.main()
