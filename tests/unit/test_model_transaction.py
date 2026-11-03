"""FEAT-059 shared multi-model transaction journal, proven with isolated dirs.

Offline only: no Creo session, no fault injection into a user design. The
persistence protocol is exercised against a temporary journal root.
"""

import tempfile
import unittest
from pathlib import Path

from creo_mechdog.model_transaction import (
    TransactionError,
    finish_model_transaction,
    load_transaction,
    prepare_model_transaction,
)

PARENT = "assembly_parent"
CHILD = "assembly_skeleton"


def result(saved=(PARENT, CHILD), verified=(PARENT, CHILD), published=True, proven=(), unproven=()):
    models = {}
    for model_id in (PARENT, CHILD):
        models[model_id] = {
            "saved": model_id in saved,
            "verified": model_id in verified,
            "revision": 5 if model_id in saved else None,
            # A model that never saved has no new checkpoint to record.
            "checkpoint": f"cp_{model_id}" if model_id in saved else None,
        }
    return {
        "models": models,
        "rollback": {"verified_models": list(proven), "unproven_models": list(unproven)},
        "registry": {
            "published": published,
            "error": None if published else "registry write failed",
        },
    }


class TransactionProtocol(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.root = Path(self._tmp.name)
        self.addCleanup(self._tmp.cleanup)

    def prepare(self, models=(PARENT, CHILD)):
        return prepare_model_transaction(
            list(models), {model_id: 4 for model_id in models}, root=self.root
        )

    def test_parent_child_identity_commit_together(self):
        record = self.prepare()
        self.assertEqual(record["stage"], "prepared")
        closed = finish_model_transaction(record["transaction_id"], result(), root=self.root)
        self.assertEqual(closed["stage"], "registry_committed")
        self.assertTrue(closed["success"])
        self.assertTrue(closed["published"])
        self.assertEqual(closed["protected_models"], [])
        self.assertEqual(closed["models"][CHILD]["revision_after"], 5)

    def test_second_save_failure_protects_all_models(self):
        record = self.prepare()
        closed = finish_model_transaction(
            record["transaction_id"],
            result(saved=(PARENT,), verified=(PARENT,), published=False, unproven=(CHILD,)),
            root=self.root,
        )
        self.assertEqual(closed["stage"], "recovery_required")
        self.assertFalse(closed["success"])
        self.assertEqual(closed["protected_models"], [PARENT, CHILD])
        # The parent saved but still needs a restore, so it is pending too; the
        # point is that neither model is reported as rolled back.
        self.assertEqual(closed["recovery"]["unproven_models"], [PARENT, CHILD])
        self.assertEqual(closed["recovery"]["verified_models"], [])

    def test_registry_publish_failure_has_recovery_record(self):
        record = self.prepare()
        closed = finish_model_transaction(
            record["transaction_id"], result(published=False), root=self.root
        )
        self.assertEqual(closed["stage"], "recovery_required")
        self.assertEqual(closed["recovery"]["reason"], "registry_publish_failed")
        self.assertEqual(closed["recovery"]["registry_error"], "registry write failed")
        self.assertFalse(closed["published"])
        self.assertEqual(closed["protected_models"], [PARENT, CHILD])

    def test_old_checkpoint_not_replaced_before_success(self):
        record = self.prepare()
        failed = finish_model_transaction(
            record["transaction_id"],
            result(saved=(PARENT,), verified=(PARENT,), published=False, unproven=(CHILD,)),
            root=self.root,
        )
        self.assertIsNone(failed["models"][CHILD]["checkpoint"] or None)
        self.assertEqual(failed["models"][PARENT]["checkpoint"], f"cp_{PARENT}")
        # The journal keeps the new checkpoint as evidence but never publishes
        # it as the committed state.
        self.assertFalse(failed["published"])

    def test_unknown_never_reported_rolled_back(self):
        record = self.prepare()
        closed = finish_model_transaction(
            record["transaction_id"],
            result(saved=(PARENT,), verified=(PARENT,), published=False, proven=(PARENT,)),
            root=self.root,
        )
        self.assertEqual(closed["models"][PARENT]["rollback"], "verified")
        self.assertEqual(closed["models"][CHILD]["rollback"], "not_attempted")
        self.assertEqual(closed["stage"], "recovery_required")
        self.assertNotIn("rolled_back", {entry["rollback"] for entry in closed["models"].values()})
        self.assertEqual(closed["protected_models"], [CHILD])

    def test_repeated_request_not_duplicate_child(self):
        record = self.prepare()
        first = finish_model_transaction(record["transaction_id"], result(), root=self.root)
        second = finish_model_transaction(record["transaction_id"], result(), root=self.root)
        self.assertTrue(second.get("idempotent"))
        self.assertEqual(first["stage"], second["stage"])
        self.assertEqual(
            load_transaction(record["transaction_id"], root=self.root)["stage"],
            "registry_committed",
        )

    def test_fully_proven_restore_closes_as_recovered(self):
        record = self.prepare()
        closed = finish_model_transaction(
            record["transaction_id"],
            result(saved=(), verified=(), published=False, proven=(PARENT, CHILD)),
            root=self.root,
        )
        self.assertEqual(closed["stage"], "recovered")
        self.assertFalse(closed["success"])
        self.assertEqual(closed["protected_models"], [])

    def test_request_shape_is_refused_before_any_write(self):
        with self.assertRaises(TransactionError):
            prepare_model_transaction([], {}, root=self.root)
        with self.assertRaises(TransactionError):
            prepare_model_transaction([PARENT, PARENT], {PARENT: 1}, root=self.root)
        with self.assertRaises(TransactionError):
            prepare_model_transaction([PARENT], {}, root=self.root)
        with self.assertRaises(TransactionError):
            prepare_model_transaction([PARENT], {PARENT: 1, CHILD: 2}, root=self.root)
        with self.assertRaises(TransactionError):
            prepare_model_transaction([PARENT], {PARENT: True}, root=self.root)
        self.assertFalse(list((self.root / "transactions").glob("*.json")))

    def test_unknown_transaction_is_refused(self):
        with self.assertRaises(TransactionError):
            load_transaction("missing", root=self.root)
        with self.assertRaises(TransactionError):
            load_transaction("../escape", root=self.root)


if __name__ == "__main__":
    unittest.main()
