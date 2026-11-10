"""C1/F08: executable contract for selective extrusion cut scope.

This is the design-stage gate. B4 implementation must import
``creo_mechdog.f08_contract`` instead of defining a second set of constants,
and must replace the "no public signature change" sentinels below once the
contract is actually enabled (with real-model acceptance evidence).
"""

import inspect
import unittest

from creo_mechdog import f08_contract, schema
from creo_mechdog.schema import validate_operations

try:
    import server
except Exception:  # pragma: no cover - import side effects are not the contract
    server = None


def cut_op(**overrides):
    operation = {
        "op": "extrude",
        "label": "deck_cut",
        "sketch": "deck_sk",
        "depth": 5,
        "mode": "cut",
    }
    operation.update(overrides)
    return operation


def scope(*ids, kind="bodies"):
    return {"kind": kind, "body_ids": list(ids)}


class F08ContractShape(unittest.TestCase):
    def test_contract_is_explicitly_design_only(self):
        self.assertEqual(f08_contract.STATUS, "designed_not_implemented")
        self.assertEqual(f08_contract.FIELD, "scope")
        self.assertIsNone(f08_contract.DEFAULT)
        self.assertEqual(f08_contract.OPERATIONS, ("extrude",))
        self.assertEqual(f08_contract.MODE, "cut")
        self.assertEqual(f08_contract.SUPPORTED_KIND, "bodies")
        self.assertEqual(f08_contract.APPLIED_RECEIPT_SOURCE, "feature_tree")

    def test_error_codes_are_unique_and_all_have_a_bounded_message(self):
        codes = f08_contract.ERROR_CODES
        self.assertEqual(len(codes), len(set(codes)))
        for code in codes:
            with self.subTest(code=code):
                message = f08_contract.error_message(code)
                self.assertTrue(message.startswith("F08_SCOPE_") is False)
                self.assertLessEqual(len(message), f08_contract.MAX_ERROR_MESSAGE_CHARS)
                self.assertNotIn("{", message)
                self.assertNotIn("}", message)

    def test_limit_note_fits_the_compact_page_and_is_a_single_source(self):
        self.assertLessEqual(len(f08_contract.LIMITATION_NOTE), 160)
        self.assertEqual(f08_contract.LIMITATION_ID, "cut_scope")
        self.assertIn("body IDs", f08_contract.LIMITATION_NOTE)
        self.assertIn("unverified", f08_contract.LIMITATION_NOTE)

    def test_compact_and_applied_receipt_fields_are_frozen(self):
        self.assertEqual(
            f08_contract.APPLIED_RECEIPT_FIELDS,
            (
                "requested_body_ids",
                "applied_body_ids",
                "source",
                "query_code",
                "non_target_bodies_unchanged",
            ),
        )
        self.assertIn("scope_applied", f08_contract.COMPACT_OPERATION_KEYS)
        self.assertIn("scope", f08_contract.PUBLIC_DOCUMENTATION_TARGETS)


class F08BackwardCompatibility(unittest.TestCase):
    def test_omitted_scope_keeps_the_existing_global_cut_receipt(self):
        verdict = f08_contract.validate_scope(cut_op())
        self.assertTrue(verdict["accepted"])
        self.assertTrue(verdict["defaulted"])
        self.assertIsNone(verdict["body_ids"])
        self.assertIsNone(verdict["code"])
        normalized = validate_operations([cut_op()])
        self.assertNotIn("scope", normalized[0])
        self.assertEqual(normalized[0]["defaulted_fields"], ["depth_type"])

    def test_explicit_scope_returns_normalized_ids_without_mutating_the_input(self):
        operation = cut_op(scope=scope(12, 13))
        verdict = f08_contract.validate_scope(operation)
        self.assertTrue(verdict["accepted"])
        self.assertFalse(verdict["defaulted"])
        self.assertEqual(verdict["body_ids"], [12, 13])
        self.assertEqual(operation["scope"], {"kind": "bodies", "body_ids": [12, 13]})

    def test_contract_does_not_reuse_boolean_targets(self):
        boolean_fields = schema.BooleanOp.model_json_schema()["properties"]
        self.assertIn("targets", boolean_fields)
        self.assertNotEqual(f08_contract.FIELD, "targets")
        self.assertNotIn("targets", f08_contract.SCOPE_ALLOWED_KEYS)
        self.assertNotIn(f08_contract.FIELD, boolean_fields)


class F08StructuredRejections(unittest.TestCase):
    def assert_rejected(self, operation, code):
        verdict = f08_contract.validate_scope(operation)
        self.assertFalse(verdict["accepted"])
        self.assertEqual(verdict["code"], code)
        self.assertIsNone(verdict["body_ids"])
        self.assertNotIn("value", verdict)
        message = f08_contract.error_message(code)
        self.assertNotIn("-5778", message)
        self.assertNotIn("2147483647", message)

    def test_non_cut_mode_and_non_extrude_are_rejected_before_any_job(self):
        self.assert_rejected(cut_op(mode="add", scope=scope(12)), "F08_SCOPE_MODE_UNSUPPORTED")
        self.assert_rejected(
            {
                "op": "boolean_bodies",
                "method": "union",
                "targets": [{"kind": "body", "id": 12}],
                "tools": [{"kind": "body", "id": 13}],
                "scope": scope(12),
            },
            "F08_SCOPE_MODE_UNSUPPORTED",
        )

    def test_malformed_shapes_and_unsupported_kinds_are_rejected(self):
        for value, code in (
            ("bodies", "F08_SCOPE_INVALID_SHAPE"),
            ({}, "F08_SCOPE_INVALID_SHAPE"),
            ({"kind": "bodies", "body_ids": []}, "F08_SCOPE_INVALID_SHAPE"),
            ({"kind": "bodies", "body_ids": "12"}, "F08_SCOPE_INVALID_SHAPE"),
            (
                {"kind": "bodies", "body_ids": [12], "target_labels": ["shell"]},
                "F08_SCOPE_INVALID_SHAPE",
            ),
            ({"kind": "feature_labels", "body_ids": [12]}, "F08_SCOPE_UNSUPPORTED_KIND"),
            ({"kind": "bodies", "body_ids": list(range(1, 102))}, "F08_SCOPE_TOO_MANY_BODIES"),
        ):
            with self.subTest(value=value):
                self.assert_rejected(cut_op(scope=value), code)

    def test_negative_zero_bool_and_duplicate_body_ids_are_rejected(self):
        for ids, code in (
            ([-5778], "F08_SCOPE_INVALID_BODY_ID"),
            ([0], "F08_SCOPE_INVALID_BODY_ID"),
            ([True], "F08_SCOPE_INVALID_BODY_ID"),
            ([12.0], "F08_SCOPE_INVALID_BODY_ID"),
            ([12, 12], "F08_SCOPE_DUPLICATE_BODY_ID"),
        ):
            with self.subTest(ids=ids):
                self.assert_rejected(cut_op(scope=scope(*ids)), code)

    def test_unverified_combinations_are_refused_instead_of_silently_ignored(self):
        self.assert_rejected(
            cut_op(depth_type="through_all", scope=scope(12)),
            "F08_SCOPE_THROUGH_ALL_UNSUPPORTED",
        )
        self.assert_rejected(
            cut_op(new_body=True, scope=scope(12)), "F08_SCOPE_NEW_BODY_UNSUPPORTED"
        )

    def test_resolve_failure_is_a_native_code_not_a_submission_validation_code(self):
        self.assertIn("F08_SCOPE_RESOLVE_FAILED", f08_contract.NATIVE_ERROR_CODES)
        self.assertNotIn("F08_SCOPE_RESOLVE_FAILED", f08_contract.SUBMISSION_ERROR_CODES)


class F08NoPublicSignatureChange(unittest.TestCase):
    """Sentinels: B4 implementation replaces these with enabled-contract tests."""

    def test_extrude_schema_still_has_no_scope_field(self):
        self.assertNotIn("scope", schema.ExtrudeOp.model_json_schema()["properties"])

    def test_creo_extrude_still_has_no_scope_parameter(self):
        if server is None:  # pragma: no cover
            self.skipTest("server import unavailable")
        self.assertNotIn("scope", inspect.signature(server.creo_extrude).parameters)

    def test_validate_operations_still_rejects_an_unknown_scope_key(self):
        with self.assertRaises(Exception):
            validate_operations([cut_op(scope=scope(12))])


if __name__ == "__main__":
    unittest.main()
