"""Unit tests for the explicit rollback_status terminal field (BUG-096 tail note)."""

from __future__ import annotations

import unittest

from creo_mechdog import rollback_status as status


class DeriveTests(unittest.TestCase):
    def test_verified_restore_is_succeeded(self):
        self.assertEqual(
            status.derive_rollback_status({"rollback_succeeded": True}), status.ROLLBACK_SUCCEEDED
        )

    def test_restore_error_is_failed(self):
        self.assertEqual(
            status.derive_rollback_status({"rollback_succeeded": False, "rollback_code": -1}),
            status.ROLLBACK_FAILED,
        )
        self.assertEqual(
            status.derive_rollback_status(
                {"rollback_message": "Restored file could not be verified"}
            ),
            status.ROLLBACK_FAILED,
        )

    def test_no_restore_evidence_is_not_attempted(self):
        # The old ambiguity: a new model has no checkpoint, native leaves the
        # default false and nothing else; that is "not attempted", not "failed".
        self.assertEqual(
            status.derive_rollback_status({"rollback_succeeded": False}),
            status.ROLLBACK_NOT_ATTEMPTED,
        )

    def test_missing_evidence_is_unconfirmed(self):
        self.assertEqual(status.derive_rollback_status({}), status.ROLLBACK_UNCONFIRMED)
        self.assertEqual(status.derive_rollback_status(None), status.ROLLBACK_UNCONFIRMED)
        self.assertEqual(status.derive_rollback_status("text"), status.ROLLBACK_UNCONFIRMED)

    def test_success_evidence_wins_over_absent_errors(self):
        self.assertEqual(
            status.derive_rollback_status({"rollback_succeeded": True, "rollback_code": 0}),
            status.ROLLBACK_SUCCEEDED,
        )


class EnsureTests(unittest.TestCase):
    def test_successful_job_is_untouched(self):
        manifest = {"status": "succeeded", "result": {"success": True}}
        status.ensure_rollback_status(manifest)
        self.assertNotIn("rollback_status", manifest["result"])

    def test_running_job_is_untouched(self):
        manifest = {"status": "running", "result": {}}
        status.ensure_rollback_status(manifest)
        self.assertNotIn("rollback_status", manifest["result"])

    def test_failed_new_model_job_reports_not_attempted(self):
        result = {"success": False, "rollback_succeeded": False}
        manifest = {"status": "failed", "result": result}
        status.ensure_rollback_status(manifest)
        self.assertEqual(result["rollback_status"], status.ROLLBACK_NOT_ATTEMPTED)

    def test_failed_saved_model_job_reports_succeeded(self):
        result = {"success": False, "rollback_succeeded": True}
        manifest = {"status": "failed", "result": result}
        status.ensure_rollback_status(manifest)
        self.assertEqual(result["rollback_status"], status.ROLLBACK_SUCCEEDED)

    def test_failed_restore_reports_failed(self):
        result = {"success": False, "rollback_succeeded": False, "rollback_code": -5}
        manifest = {"status": "failed", "result": result}
        status.ensure_rollback_status(manifest)
        self.assertEqual(result["rollback_status"], status.ROLLBACK_FAILED)

    def test_unknown_outcome_without_result_is_untouched(self):
        manifest = {"status": "unknown_outcome"}
        status.ensure_rollback_status(manifest)
        self.assertNotIn("result", manifest)

    def test_unknown_outcome_synthesized_result_is_unconfirmed(self):
        manifest = {"status": "unknown_outcome", "result": {"failed_model_cleanup": {}}}
        status.ensure_rollback_status(manifest)
        self.assertEqual(manifest["result"]["rollback_status"], status.ROLLBACK_UNCONFIRMED)

    def test_delivered_value_in_vocabulary_is_preserved(self):
        result = {"rollback_succeeded": False, "rollback_status": status.ROLLBACK_FAILED}
        manifest = {"status": "failed", "result": result}
        status.ensure_rollback_status(manifest)
        self.assertEqual(result["rollback_status"], status.ROLLBACK_FAILED)

    def test_malformed_delivered_value_degrades_to_unconfirmed(self):
        result = {"rollback_succeeded": True, "rollback_status": "ok"}
        manifest = {"status": "failed", "result": result}
        status.ensure_rollback_status(manifest)
        # A broken receipt never reads as a successful restore, even when the
        # boolean says true: the field is not silently rewritten to succeeded.
        self.assertEqual(result["rollback_status"], status.ROLLBACK_UNCONFIRMED)

    def test_rollback_succeeded_keeps_its_value(self):
        result = {"rollback_succeeded": False}
        manifest = {"status": "failed", "result": result}
        status.ensure_rollback_status(manifest)
        self.assertIs(result["rollback_succeeded"], False)


if __name__ == "__main__":
    unittest.main()
