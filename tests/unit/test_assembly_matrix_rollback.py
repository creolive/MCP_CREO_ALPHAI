"""FEAT-012 matrix driver failed-rollback verification (offline).

The live run build/assembly_matrix_live_20261025T151808Z (guard
build/guarded_live_20261025T151807442040) got a genuinely failed job —
the preset compound move + remove invalid native component 424242 job
47d5dfc90089459080fb5a0b7e57674a — whose manifest LEGITIMATELY has no
top-level ``revision`` while rollback_succeeded stayed true and
inspection_source reported "rollback_verified". The old driver line
``assert failed["revision"] == assembly["revision"]`` raised KeyError,
aborting the suite before the remaining assertions ran.

These tests lock the corrected behavior: the model revision is verified
from an actual creo_list_components query (``after.revision``) against
the pre-failure assembly revision and snapshot; the failed manifest's own
revision is checked only when the field is actually present; no default
success value is fabricated for the missing field.
"""

import unittest

from creo_mechdog.operation_results import normalize_operations
from creo_mechdog.schema import validate_operations
from tools.test_assembly_matrix import verify_rolled_back_failure

ASSEMBLY_REVISION = 34

# R05: the 17.9-degree row-vector pose rounded to six decimals (still inside the
# 1e-6 orthogonality/determinant gate, so it must never be "fixed" by the caller).
ROTATION_17_9 = [
    [0.951594, 0.307357, 0.0],
    [-0.307357, 0.951594, 0.0],
    [0.0, 0.0, 1.0],
]


def failed_manifest(revision=...):
    """Shape copied from the unmodified live evidence report."""
    manifest = {
        "job_id": "47d5dfc90089459080fb5a0b7e57674a",
        "status": "failed",
        "result": {
            "rollback_succeeded": True,
            "inspection_source": "rollback_verified",
            "saved_file_reloaded_and_verified": False,
            "toolkit_code": -23,
        },
        "component_changes": {
            "status": "rolled_back",
            "changes": [
                {"op": "moved", "label": "matrix_0"},
                {"op": "removed", "label": None},
            ],
            "note": "The job failed after native execution; the saved checkpoint "
            "was restored and verified (rollback_succeeded).",
        },
    }
    if revision is not ...:
        manifest["revision"] = revision
    return manifest


def listed(revision=ASSEMBLY_REVISION):
    return {"model_id": "c298b819c09b45ed85fd85754a2fbe98", "revision": revision, "components": []}


class RolledBackFailureVerification(unittest.TestCase):
    def test_revision_less_manifest_matches_unmodified_live_evidence(self):
        failed = failed_manifest()
        self.assertNotIn("revision", failed)  # the field the old driver assumed
        with self.assertRaises(KeyError):
            # Reproduces the original defect before the fix.
            _ = failed["revision"]
        verify_rolled_back_failure(failed, ASSEMBLY_REVISION, listed(), listed())

    def test_manifest_with_matching_revision_also_passes(self):
        verify_rolled_back_failure(
            failed_manifest(revision=ASSEMBLY_REVISION), ASSEMBLY_REVISION, listed(), listed()
        )

    def test_manifest_with_mismatched_revision_fails(self):
        with self.assertRaises(AssertionError):
            verify_rolled_back_failure(
                failed_manifest(revision=35), ASSEMBLY_REVISION, listed(), listed()
            )

    def test_queried_after_revision_must_match_assembly(self):
        # The actual MCP list_components readout says the model moved on.
        with self.assertRaises(AssertionError):
            verify_rolled_back_failure(failed_manifest(), ASSEMBLY_REVISION, listed(), listed(35))

    def test_before_after_snapshot_inequality_fails(self):
        before = listed()
        after = dict(listed(), components=[{"feature_id": 1}])
        with self.assertRaises(AssertionError):
            verify_rolled_back_failure(failed_manifest(), ASSEMBLY_REVISION, before, after)

    def test_rollback_not_succeeded_fails(self):
        failed = failed_manifest()
        failed["result"]["rollback_succeeded"] = False
        with self.assertRaises(AssertionError):
            verify_rolled_back_failure(failed, ASSEMBLY_REVISION, listed(), listed())

    def test_component_changes_not_rolled_back_fails(self):
        failed = failed_manifest()
        failed["component_changes"]["status"] = "committed"
        with self.assertRaises(AssertionError):
            verify_rolled_back_failure(failed, ASSEMBLY_REVISION, listed(), listed())

    def test_unexpected_success_status_fails(self):
        failed = failed_manifest(revision=ASSEMBLY_REVISION)
        failed["status"] = "succeeded"
        with self.assertRaises(AssertionError):
            verify_rolled_back_failure(failed, ASSEMBLY_REVISION, listed(), listed())


def matrix_failed_manifest():
    """R05: the same rolled-back job, with its placement failure context."""
    manifest = failed_manifest()
    manifest["result"].update(
        {
            "failed_operation_index": 1,
            "failed_operation": {
                "index": 1,
                "operation": "component_placement",
                "stage": "execute_component_placement",
                "feature_label": "i032",
                "sketch_name": None,
                "toolkit_call": "ProAsmcompPositionSet",
                "pro_error": -2,
                "pro_error_source": "toolkit",
                "input_matrix": [row + [0.0] for row in ROTATION_17_9] + [[0.0, 0.0, 0.0, 1.0]],
                "matrix_source": "rotation_matrix",
                "determinant": 1.0,
                "orthogonality_residual": 5.4e-7,
                "message": "Toolkit call ProAsmcompPositionSet failed with code -2",
                "message_truncated": False,
            },
        }
    )
    return manifest


class MatrixFailureRollback(unittest.TestCase):
    """R05: a refused matrix costs the whole batch, never a partial commit."""

    def test_the_matrix_context_survives_the_rollback_check(self):
        failed = matrix_failed_manifest()
        verify_rolled_back_failure(failed, ASSEMBLY_REVISION, listed(), listed())
        block = failed["result"]["failed_operation"]
        self.assertEqual(block["operation"], "component_placement")
        self.assertEqual(block["toolkit_call"], "ProAsmcompPositionSet")
        # The caller's matrix is echoed untouched, with its measured arithmetic.
        self.assertEqual(block["input_matrix"][:3], [row + [0.0] for row in ROTATION_17_9])
        self.assertAlmostEqual(block["determinant"], 1.0, delta=1e-6)
        self.assertLess(block["orthogonality_residual"], 1e-6)
        self.assertNotIn("revision", failed)

    def test_a_trailing_operation_is_rolled_back_or_not_executed(self):
        operations = [
            {"index": 0, "op": "assemble_component", "succeeded": True},
            {"index": 1, "op": "component_placement", "succeeded": False},
            {
                "index": 2,
                "op": "component_placement",
                "succeeded": False,
                "execution_status": "not_executed",
            },
        ]
        normalized = normalize_operations(
            operations,
            job_status="failed",
            rollback_confirmed=True,
            failed_index=1,
        )
        self.assertEqual(
            [op["effect_status"] for op in normalized], ["rolled_back", "rolled_back", "no_effect"]
        )
        self.assertEqual(normalized[0]["execution_status"], "succeeded")
        self.assertEqual(normalized[1]["execution_status"], "failed")

    def test_a_legal_edit_after_the_rollback_keeps_the_same_revision(self):
        verify_rolled_back_failure(matrix_failed_manifest(), ASSEMBLY_REVISION, listed(), listed())
        # The rollback restored revision 34, so the planned follow-up edit is
        # admitted against 34 and only its own commit advances the model.
        follow_up = {
            "op": "component_placement",
            "component": "i032",
            "rotation_matrix": ROTATION_17_9,
        }
        validate_operations([follow_up])
        self.assertEqual(listed()["revision"], ASSEMBLY_REVISION)
        self.assertEqual(ASSEMBLY_REVISION + 1, 35)
        # The stale check still matters: once the edit lands, 34 no longer
        # describes the model.
        with self.assertRaises(AssertionError):
            verify_rolled_back_failure(
                matrix_failed_manifest(), ASSEMBLY_REVISION, listed(), listed(35)
            )


if __name__ == "__main__":
    unittest.main()
