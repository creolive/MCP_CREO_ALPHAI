"""BUG-114: one scoped terminal-effect decision for failed jobs.

The tests pin three properties:

* a fully proven erasure of the job's own never-saved new model clears only
  the managed model/component scope, never an exported file;
* every veto, partial receipt, untrusted operation trail and true
  ``unknown_outcome`` stays unknown;
* per-operation ``execution_status`` and the legacy rollback fields are never
  rewritten by the new verdict.
"""

from __future__ import annotations

import unittest

from creo_mechdog import component_changes, operation_results, terminal_effect


def clean_receipt(**overrides) -> dict:
    receipt = {
        "attempted": True,
        "status": "erased",
        "reason": "cleaned",
        "erase_code": 0,
        "absence_verified": True,
    }
    receipt.update(overrides)
    return receipt


def result_with(receipt: dict | None, records: list[dict], **extra) -> dict:
    result = {"success": False, **extra}
    if receipt is not None:
        result["failed_model_cleanup"] = receipt
    result["operations"] = records
    return result


def classify(
    result,
    *,
    job_status="failed",
    is_new_model=True,
    checkpoint_present=False,
    operations=None,
    scope="managed_model",
):
    return terminal_effect.classify_terminal_effect(
        result,
        job_status=job_status,
        is_new_model=is_new_model,
        checkpoint_present=checkpoint_present,
        operations=operations,
        effect_scope=scope,
    )


class ConfirmedCleanupTests(unittest.TestCase):
    def test_confirmed_new_model_cleanup_has_no_model_effect(self):
        request = [{"op": "sketch"}, {"op": "extrude"}]
        result = result_with(
            clean_receipt(),
            [
                {
                    "op": "sketch",
                    "index": 0,
                    "execution_status": "succeeded",
                    "effect_status": "no_effect",
                },
                {
                    "op": "extrude",
                    "index": 1,
                    "execution_status": "failed",
                    "effect_status": "no_effect",
                },
            ],
        )
        model = classify(result, operations=request)
        self.assertEqual(
            ("no_effect", "confirmed", "new_model_cleanup_confirmed", "managed_model"),
            (model["effect"], model["status"], model["reason"], model["scope"]),
        )
        components = classify(result, operations=request, scope="component_bindings")
        self.assertEqual("no_effect", components["effect"])
        external = classify(result, operations=request, scope="external_outputs")
        self.assertEqual(
            ("no_effect", "no_external_outputs_requested"), (external["effect"], external["reason"])
        )
        # Execution facts and the legacy rollback keys are untouched.
        self.assertEqual(
            [record["execution_status"] for record in result["operations"]],
            ["succeeded", "failed"],
        )
        self.assertNotIn("rollback_succeeded", result)

    def test_apply_to_result_publishes_three_scopes(self):
        request = [{"op": "extrude"}]
        result = result_with(
            clean_receipt(),
            [{"op": "extrude", "index": 0, "execution_status": "failed"}],
        )
        terminal_effect.apply_to_result(
            result,
            job_status="failed",
            is_new_model=True,
            checkpoint_present=False,
            operations=request,
        )
        self.assertEqual(
            {"managed_model", "component_bindings", "external_outputs"},
            set(result["terminal_effect"]),
        )
        self.assertEqual("no_effect", result["terminal_effect"]["managed_model"]["effect"])

    def test_succeeded_and_running_results_gain_no_block(self):
        for status in ("succeeded", "running", "queued"):
            result = {"success": status == "succeeded"}
            terminal_effect.apply_to_result(result, job_status=status, operations=[])
            self.assertNotIn("terminal_effect", result)

    def test_component_summary_reports_no_effect(self):
        result = result_with(
            clean_receipt(),
            [{"op": "assemble_component", "index": 0, "execution_status": "failed"}],
        )
        summary = component_changes.summarize(
            [{"op": "assemble_component", "label": "part_a"}],
            job_status="failed",
            rollback=result,
            executed=True,
            is_new_model=True,
            checkpoint_present=False,
        )
        self.assertIsNotNone(summary)
        self.assertEqual("no_effect", summary["status"])
        self.assertEqual([], summary["changes"])
        self.assertIn("failed_model_cleanup", summary["note"])


class ExportPreservationTests(unittest.TestCase):
    def test_cleanup_does_not_erase_prior_export_effect(self):
        request = [{"op": "export"}, {"op": "extrude"}]
        result = result_with(
            clean_receipt(),
            [
                {
                    "op": "export",
                    "index": 0,
                    "execution_status": "succeeded",
                    "effect_status": "unknown",
                },
                {
                    "op": "extrude",
                    "index": 1,
                    "execution_status": "failed",
                    "effect_status": "no_effect",
                },
            ],
        )
        external = classify(result, operations=request, scope="external_outputs")
        self.assertEqual(
            ("unknown", "unconfirmed", "external_outputs_retained_after_cleanup"),
            (external["effect"], external["status"], external["reason"]),
        )
        self.assertEqual("no_effect", classify(result, operations=request)["effect"])

    def test_cleanup_does_not_publish_an_export_as_no_effect(self):
        normalized = operation_results.normalize_operations(
            [
                {"op": "export", "execution_status": "succeeded"},
                {"op": "extrude", "execution_status": "failed"},
            ],
            job_status="failed",
            cleanup_confirmed=True,
        )
        self.assertEqual(
            ["unknown", "no_effect"],
            [record["effect_status"] for record in normalized],
        )

    def test_unexecuted_export_stays_no_effect(self):
        request = [{"op": "extrude"}, {"op": "export"}]
        result = result_with(
            clean_receipt(),
            [
                {"op": "extrude", "index": 0, "execution_status": "failed"},
                {"op": "export", "index": 1, "execution_status": "not_executed"},
            ],
        )
        external = classify(result, operations=request, scope="external_outputs")
        self.assertEqual(
            ("no_effect", "external_outputs_not_executed"),
            (external["effect"], external["reason"]),
        )


class DecisionTableTests(unittest.TestCase):
    def test_checkpoint_restore_is_rolled_back(self):
        request = [{"op": "extrude"}]
        result = result_with(
            None,
            [{"op": "extrude", "index": 0, "execution_status": "succeeded"}],
            rollback_succeeded=True,
        )
        verdict = classify(result, is_new_model=False, checkpoint_present=True, operations=request)
        self.assertEqual(
            ("rolled_back", "confirmed", "checkpoint_restored"),
            (verdict["effect"], verdict["status"], verdict["reason"]),
        )

    def test_rollback_evidence_without_checkpoint_does_not_resolve(self):
        request = [{"op": "extrude"}]
        result = result_with(
            None,
            [{"op": "extrude", "index": 0, "execution_status": "succeeded"}],
            rollback_succeeded=True,
        )
        verdict = classify(result, checkpoint_present=False, operations=request)
        self.assertEqual(
            ("unknown", "rollback_evidence_without_checkpoint"),
            (verdict["effect"], verdict["reason"]),
        )

    def test_preflight_refusal_is_no_effect(self):
        request = [{"op": "extrude"}]
        result = result_with(
            None,
            [{"op": "extrude", "index": 0, "execution_status": "not_executed"}],
            model_unchanged=True,
        )
        verdict = classify(result, operations=request)
        self.assertEqual(
            ("no_effect", "no_mutation_before_modeling"), (verdict["effect"], verdict["reason"])
        )

    def test_erase_code_zero_alone_is_insufficient(self):
        request = [{"op": "extrude"}]
        records = [{"op": "extrude", "index": 0, "execution_status": "failed"}]
        for receipt in (
            clean_receipt(absence_verified=False),
            clean_receipt(status="unknown"),
            clean_receipt(reason="erase_unconfirmed"),
            clean_receipt(attempted=False),
            clean_receipt(erase_code=None),
            clean_receipt(erase_code=True),
        ):
            with self.subTest(receipt=receipt):
                verdict = classify(result_with(receipt, records), operations=request)
                self.assertEqual("unknown", verdict["effect"])

    def test_absence_flag_alone_is_insufficient(self):
        request = [{"op": "extrude"}]
        result = result_with(
            {"attempted": True, "status": "erased", "reason": "cleaned", "absence_verified": True},
            [{"op": "extrude", "index": 0, "execution_status": "failed"}],
        )
        verdict = classify(result, operations=request)
        self.assertEqual(("unknown", "unconfirmed"), (verdict["effect"], verdict["status"]))

    def test_veto_reasons_are_surfaced_and_not_upgraded(self):
        request = [{"op": "extrude"}]
        records = [{"op": "extrude", "index": 0, "execution_status": "failed"}]
        for reason in ("preexisting_same_name", "saved_since_creation", "not_new_model_job"):
            with self.subTest(reason=reason):
                receipt = {
                    "attempted": True,
                    "status": "skipped",
                    "reason": reason,
                    "erase_code": None,
                    "absence_verified": False,
                }
                verdict = classify(result_with(receipt, records), operations=request)
                self.assertEqual(("unknown", reason), (verdict["effect"], verdict["reason"]))

    def test_cleaned_receipt_on_an_existing_model_is_not_trusted(self):
        request = [{"op": "extrude"}]
        result = result_with(
            clean_receipt(),
            [{"op": "extrude", "index": 0, "execution_status": "failed"}],
        )
        verdict = classify(result, is_new_model=False, checkpoint_present=True, operations=request)
        self.assertEqual(("unknown", "not_new_model_job"), (verdict["effect"], verdict["reason"]))

    def test_partial_terminal_trail_never_upgrades(self):
        request = [{"op": "sketch"}, {"op": "extrude"}]
        receipt = clean_receipt()
        for records in (
            [],
            [{"op": "sketch", "index": 0, "execution_status": "succeeded"}],
            [{"op": "extrude", "index": 0, "execution_status": "failed"}],
            [
                {"op": "sketch", "index": 0, "execution_status": "succeeded"},
                {"op": "extrude", "index": 1},
            ],
            [
                {"op": "sketch", "index": 1, "execution_status": "succeeded"},
                {"op": "extrude", "index": 0, "execution_status": "failed"},
            ],
        ):
            with self.subTest(records=records):
                verdict = classify(result_with(receipt, records), operations=request)
                self.assertEqual(
                    ("unknown", "terminal_operations_untrusted"),
                    (verdict["effect"], verdict["reason"]),
                )
        missing_operations = classify(result_with(receipt, records), operations=None)
        self.assertEqual("unknown", missing_operations["effect"])

    def test_unknown_outcome_is_never_rewritten_by_read_side(self):
        request = [{"op": "extrude"}]
        result = result_with(
            clean_receipt(),
            [{"op": "extrude", "index": 0, "execution_status": "succeeded"}],
        )
        terminal_effect.apply_to_result(
            result,
            job_status="unknown_outcome",
            is_new_model=True,
            checkpoint_present=False,
            operations=request,
        )
        for verdict in result["terminal_effect"].values():
            self.assertEqual(
                ("unknown", "unknown", "unknown_outcome"),
                (verdict["effect"], verdict["status"], verdict["reason"]),
            )

    def test_unknown_scope_is_never_guessed(self):
        verdict = classify({"success": False}, operations=[], scope="something_else")
        self.assertEqual(
            ("unknown", "unknown", "unknown_effect_scope", "unknown"),
            (verdict["effect"], verdict["status"], verdict["reason"], verdict["scope"]),
        )


if __name__ == "__main__":
    unittest.main()
