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

from tools.test_assembly_matrix import verify_rolled_back_failure

ASSEMBLY_REVISION = 34


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


if __name__ == "__main__":
    unittest.main()
