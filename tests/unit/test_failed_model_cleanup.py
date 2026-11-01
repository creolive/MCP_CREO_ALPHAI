"""BUG-096 (Q03/E): safe cleanup of failed new-model orphans — policy contract.

The failing job in feedback chapter E leaves an unsaved session object that
blocks the next same-name model (``New model name already exists in the Creo
session``). Cleanup may erase exactly one object: the session model proven to
be created by the failed job itself. Everything else keeps.

All Creo behaviour is simulated by isolated stubs (plain dicts). No test here
touches Creo, a session, a window, or any real object. The normative policy
lives in ``creo_mechdog.failed_model_cleanup``; ``native/generic.cpp`` mirrors
its reason vocabulary and must never claim ``absence_verified`` without
running the absence queries.

Counterexamples that must never be erased (one test each):
pre-existing same-name object, user-modified object, window-open object,
assembly-referenced object, erase call failure, absence query failure and
unknown outcome. ``rollback_*`` keeps its old restore-checkpoint meaning and
is never conflated with this cleanup block.
"""

from __future__ import annotations

import unittest

import bridge
from creo_mechdog import failed_model_cleanup as cleanup


def candidate(**overrides) -> dict:
    """A fully-proven job-created orphan; individual probes can be broken."""
    evidence = {
        "created_by_job": True,
        "identity_matches": True,
        "never_saved": True,
        "window_open": False,
        "user_modified": False,
        "referenced_by_other": False,
        "safety_query_failed": False,
    }
    evidence.update(overrides)
    return evidence


def receipt(**overrides) -> dict:
    """A receipt with the exact five-field shape the contract mandates."""
    value = {
        "attempted": True,
        "status": "erased",
        "reason": "cleaned",
        "erase_code": 0,
        "absence_verified": True,
    }
    value.update(overrides)
    return value


class CandidateSafetyPolicy(unittest.TestCase):
    """evaluate_candidate: the veto chain over stubbed Creo probes."""

    def test_proven_orphan_is_erased(self):
        decision = cleanup.evaluate_candidate(candidate())
        self.assertEqual(decision, {"action": "erase", "reason": "cleaned"})

    def test_preexisting_same_name_object_is_kept(self):
        # E's rename-conflict victim: the name holder predates this job.
        decision = cleanup.evaluate_candidate(candidate(created_by_job=False))
        self.assertEqual(decision, {"action": "keep", "reason": "preexisting_same_name"})

    def test_user_modified_object_is_kept(self):
        decision = cleanup.evaluate_candidate(candidate(user_modified=True))
        self.assertEqual(decision, {"action": "keep", "reason": "user_modified"})

    def test_window_open_object_is_kept(self):
        decision = cleanup.evaluate_candidate(candidate(window_open=True))
        self.assertEqual(decision, {"action": "keep", "reason": "window_open"})

    def test_assembly_referenced_object_is_kept(self):
        decision = cleanup.evaluate_candidate(candidate(referenced_by_other=True))
        self.assertEqual(decision, {"action": "keep", "reason": "referenced_by_other"})

    def test_safety_query_failure_keeps_object(self):
        # 无证明就保留: an errored probe proves nothing, so nothing is erased.
        decision = cleanup.evaluate_candidate(candidate(safety_query_failed=True))
        self.assertEqual(decision, {"action": "keep", "reason": "safety_query_failed"})

    def test_identity_change_keeps_object(self):
        decision = cleanup.evaluate_candidate(candidate(identity_matches=False))
        self.assertEqual(decision, {"action": "keep", "reason": "identity_changed"})

    def test_saved_since_creation_keeps_object(self):
        decision = cleanup.evaluate_candidate(candidate(never_saved=False))
        self.assertEqual(decision, {"action": "keep", "reason": "saved_since_creation"})

    def test_not_job_created_dominates_every_other_signal(self):
        # A pre-existing object is never erased, whatever else the probes say.
        decision = cleanup.evaluate_candidate(
            candidate(created_by_job=False, user_modified=True, window_open=True)
        )
        self.assertEqual(decision, {"action": "keep", "reason": "preexisting_same_name"})

    def test_probe_failure_dominates_observed_vetoes(self):
        # When probes errored, the honest reason is the failed proof itself.
        decision = cleanup.evaluate_candidate(
            candidate(safety_query_failed=True, window_open=True, referenced_by_other=True)
        )
        self.assertEqual(decision, {"action": "keep", "reason": "safety_query_failed"})

    def test_veto_precedence_is_deterministic(self):
        decision = cleanup.evaluate_candidate(
            candidate(window_open=True, user_modified=True, referenced_by_other=True)
        )
        self.assertEqual(decision, {"action": "keep", "reason": "window_open"})

    def test_incomplete_evidence_is_refused(self):
        # A probe that never ran is not a probe that returned "safe".
        with self.assertRaises(ValueError):
            cleanup.evaluate_candidate(
                {key: True for key in ("created_by_job", "identity_matches")}
            )

    def test_non_boolean_probe_is_refused(self):
        with self.assertRaises(ValueError):
            cleanup.evaluate_candidate(candidate(created_by_job=1))


class ReceiptContract(unittest.TestCase):
    """validate_receipt: the five-field native receipt, enforced strictly."""

    def test_every_documented_reason_shape_is_accepted(self):
        for reason, shape in cleanup.RECEIPT_SHAPES.items():
            with self.subTest(reason=reason):
                code = -3 if shape["erase_code"] == "nonzero" else shape["erase_code"]
                value = receipt(
                    attempted=shape["attempted"],
                    status=shape["status"],
                    reason=reason,
                    erase_code=code,
                    absence_verified=shape["absence_verified"],
                )
                self.assertEqual(cleanup.validate_receipt(value), value)

    def test_erased_requires_verified_absence(self):
        with self.assertRaises(ValueError):
            cleanup.validate_receipt(receipt(absence_verified=False))

    def test_veto_reason_may_not_claim_verified_absence(self):
        # 查询没执行时不得填成功: a kept object was never queried as absent.
        with self.assertRaises(ValueError):
            cleanup.validate_receipt(
                receipt(
                    status="skipped", reason="user_modified", erase_code=None, absence_verified=True
                )
            )

    def test_erased_without_erase_attempt_code_is_rejected(self):
        with self.assertRaises(ValueError):
            cleanup.validate_receipt(receipt(erase_code=None))
        with self.assertRaises(ValueError):
            cleanup.validate_receipt(receipt(erase_code=-3))

    def test_erase_failure_keeps_raw_code_and_no_absence_claim(self):
        value = receipt(
            status="failed",
            reason="erase_failed",
            erase_code=-3,
            absence_verified=False,
        )
        self.assertEqual(cleanup.validate_receipt(value), value)

    def test_erase_failure_with_zero_code_is_rejected(self):
        with self.assertRaises(ValueError):
            cleanup.validate_receipt(receipt(status="failed", reason="erase_failed", erase_code=0))

    def test_absence_query_failure_stays_unknown(self):
        value = receipt(
            status="unknown",
            reason="erase_unconfirmed",
            erase_code=0,
            absence_verified=False,
        )
        self.assertEqual(cleanup.validate_receipt(value), value)

    def test_unknown_status_may_not_claim_verified_absence(self):
        with self.assertRaises(ValueError):
            cleanup.validate_receipt(
                receipt(
                    status="unknown",
                    reason="erase_unconfirmed",
                    erase_code=0,
                    absence_verified=True,
                )
            )

    def test_skipped_reasons_carry_no_erase_code(self):
        with self.assertRaises(ValueError):
            cleanup.validate_receipt(
                receipt(
                    status="skipped", reason="window_open", erase_code=-1, absence_verified=False
                )
            )

    def test_unknown_reason_shapes_are_accepted(self):
        for value in (cleanup.receipt_unknown_outcome(), cleanup.receipt_not_reported()):
            self.assertEqual(cleanup.validate_receipt(value), value)

    def test_reason_status_mismatch_is_rejected(self):
        with self.assertRaises(ValueError):
            cleanup.validate_receipt(receipt(status="failed", reason="cleaned"))

    def test_unknown_reason_is_rejected(self):
        with self.assertRaises(ValueError):
            cleanup.validate_receipt(receipt(reason="just_an_orphan"))

    def test_missing_or_extra_keys_are_rejected(self):
        broken = receipt()
        del broken["erase_code"]
        with self.assertRaises(ValueError):
            cleanup.validate_receipt(broken)
        with self.assertRaises(ValueError):
            cleanup.validate_receipt({**receipt(), "bonus": 1})

    def test_wrong_types_are_rejected(self):
        for field, wrong in (
            ("attempted", 1),
            ("status", True),
            ("reason", 7),
            ("erase_code", True),
            ("absence_verified", "true"),
        ):
            with self.subTest(field=field):
                with self.assertRaises(ValueError):
                    cleanup.validate_receipt(receipt(**{field: wrong}))

    def test_non_dict_is_rejected(self):
        for raw in (None, [], "erased", 0):
            with self.subTest(raw=raw):
                with self.assertRaises(ValueError):
                    cleanup.validate_receipt(raw)


class NormalizeReceipt(unittest.TestCase):
    """normalize_receipt: a contract break degrades honestly, never to success."""

    def test_valid_receipt_passes_through_with_exact_keys(self):
        normalized = cleanup.normalize_receipt(receipt())
        self.assertEqual(normalized, receipt())
        self.assertEqual(set(normalized), set(cleanup.RECEIPT_KEYS))

    def test_invalid_receipt_degrades_to_unproven_unknown(self):
        normalized = cleanup.normalize_receipt(receipt(absence_verified=False))
        self.assertEqual(normalized["status"], "unknown")
        self.assertEqual(normalized["reason"], "invalid_receipt")
        self.assertFalse(normalized["absence_verified"])
        self.assertFalse(normalized["attempted"])


class TerminalRegistration(unittest.TestCase):
    """ensure_terminal_receipt: bridge-side terminal state stays honest."""

    def test_unknown_outcome_without_result_reports_no_cleanup_claim(self):
        manifest = {"status": "unknown_outcome", "kind": "generic"}
        cleanup.ensure_terminal_receipt(manifest)
        value = manifest["result"]["failed_model_cleanup"]
        self.assertEqual(cleanup.validate_receipt(value), cleanup.receipt_unknown_outcome())
        self.assertFalse(value["absence_verified"])
        self.assertEqual(value["status"], "unknown")

    def test_unknown_outcome_with_result_but_no_block_is_not_reported(self):
        manifest = {"status": "unknown_outcome", "kind": "generic", "result": {"success": False}}
        cleanup.ensure_terminal_receipt(manifest)
        value = manifest["result"]["failed_model_cleanup"]
        self.assertEqual(value, cleanup.receipt_not_reported())
        self.assertFalse(value["absence_verified"])

    def test_unknown_outcome_keeps_a_delivered_native_block(self):
        # The worker ran the cleanup before delivery failed; its proof stands.
        block = receipt()
        manifest = {"status": "unknown_outcome", "kind": "generic", "result": {"success": False}}
        manifest["result"]["failed_model_cleanup"] = dict(block)
        cleanup.ensure_terminal_receipt(manifest)
        self.assertEqual(manifest["result"]["failed_model_cleanup"], block)

    def test_failed_result_without_block_is_not_reported(self):
        manifest = {"status": "failed", "kind": "generic", "result": {"success": False}}
        cleanup.ensure_terminal_receipt(manifest)
        value = manifest["result"]["failed_model_cleanup"]
        self.assertEqual(value, cleanup.receipt_not_reported())
        self.assertFalse(value["absence_verified"])

    def test_failed_result_invalid_block_is_downgraded(self):
        manifest = {
            "status": "failed",
            "kind": "generic",
            "result": {
                "success": False,
                "failed_model_cleanup": receipt(status="skipped", reason="cleaned"),
            },
        }
        cleanup.ensure_terminal_receipt(manifest)
        value = manifest["result"]["failed_model_cleanup"]
        self.assertEqual(value["reason"], "invalid_receipt")
        self.assertFalse(value["absence_verified"])

    def test_succeeded_job_is_never_touched(self):
        manifest = {"status": "succeeded", "kind": "generic", "result": {"success": True}}
        cleanup.ensure_terminal_receipt(manifest)
        self.assertNotIn("failed_model_cleanup", manifest["result"])

    def test_rollback_fields_keep_their_old_semantics(self):
        # Cleanup is not restore-from-checkpoint: the two blocks coexist and
        # neither may be derived from the other.
        result = {
            "success": False,
            "rollback_succeeded": False,
            "rollback_message": "new model has no saved checkpoint",
            "failed_model_cleanup": receipt(),
        }
        manifest = {"status": "failed", "kind": "generic", "result": result}
        cleanup.ensure_terminal_receipt(manifest)
        self.assertIs(manifest["result"]["rollback_succeeded"], False)
        self.assertEqual(
            manifest["result"]["rollback_message"], "new model has no saved checkpoint"
        )
        self.assertTrue(manifest["result"]["failed_model_cleanup"]["absence_verified"])

    def test_compact_projection_keeps_the_receipt(self):
        summary = bridge.compact_job(
            {
                "job_id": "j",
                "kind": "generic",
                "status": "failed",
                "result": {"success": False, "failed_model_cleanup": receipt()},
            }
        )
        self.assertEqual(summary["result"]["failed_model_cleanup"], receipt())


if __name__ == "__main__":
    unittest.main()
