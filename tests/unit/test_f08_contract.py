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
        self.assertEqual(f08_contract.STATUS, "implemented")
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
        self.assertIn("body ID", f08_contract.LIMITATION_NOTE)
        # B4 turned the design-stage "unverified" wording into an evidenced
        # refusal: one body per cut, the rest split into further operations.
        self.assertIn("unsupported", f08_contract.LIMITATION_NOTE)

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
        operation = cut_op(scope=scope(12))
        verdict = f08_contract.validate_scope(operation)
        self.assertTrue(verdict["accepted"])
        self.assertFalse(verdict["defaulted"])
        self.assertEqual(verdict["body_ids"], [12])
        self.assertEqual(operation["scope"], {"kind": "bodies", "body_ids": [12]})
        self.assertEqual(f08_contract.MAX_BODY_IDS, 1)

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


class F08PublicSurfaceEnabled(unittest.TestCase):
    """B4 replaced the design sentinels: the field, the tool parameter and the
    plan path are live, and one target body per cut is enforced by the contract."""

    def test_extrude_schema_carries_scope(self):
        properties = schema.ExtrudeOp.model_json_schema()["properties"]
        self.assertIn("scope", properties)
        self.assertEqual(
            schema.ExtrudeScope.model_json_schema()["properties"]["kind"]["const"], "bodies"
        )

    def test_creo_extrude_exposes_scope(self):
        if server is None:  # pragma: no cover
            self.skipTest("server import unavailable")
        self.assertIn("scope", inspect.signature(server.creo_extrude).parameters)

    def test_plan_path_accepts_one_body_and_keeps_it(self):
        dumped = validate_operations([cut_op(scope=scope(7))])
        self.assertEqual(dumped[0]["scope"], {"kind": "bodies", "body_ids": [7]})

    def test_plan_path_rejects_several_bodies_before_any_job(self):
        with self.assertRaises(ValueError) as caught:
            validate_operations([cut_op(scope=scope(7, 8))])
        self.assertIn("exactly one target body", str(caught.exception))

    def test_plan_path_rejects_scope_outside_cut(self):
        with self.assertRaises(ValueError) as caught:
            validate_operations([cut_op(mode="add", scope=scope(7))])
        self.assertIn("only to extrude cuts", str(caught.exception))

    def test_plan_path_rejects_scope_with_through_all(self):
        with self.assertRaises(ValueError) as caught:
            validate_operations([cut_op(depth_type="through_all", scope=scope(7))])
        self.assertIn("through_all", str(caught.exception))

    def test_plan_path_rejects_scope_on_a_surface_extrude(self):
        with self.assertRaises(ValueError) as caught:
            validate_operations([cut_op(mode="surface", scope=scope(7))])
        self.assertIn("only to extrude cuts", str(caught.exception))

    def test_plan_path_refuses_a_scope_list_beyond_the_shape_limit(self):
        # The schema bound refuses absurd lists before the contract counts them;
        # either way nothing reaches a job, which is what the boundary promises.
        with self.assertRaises(ValueError):
            validate_operations([cut_op(scope=scope(*range(1, 102)))])

    def test_plan_without_scope_is_unchanged(self):
        dumped = validate_operations([cut_op()])
        self.assertNotIn("scope", dumped[0])


class F08NativeWiring(unittest.TestCase):
    """The native executor owns the applied evidence; these are source sentinels
    that fail if the cut branch silently drops the scope or the readback."""

    def setUp(self):
        from pathlib import Path

        self.source = (Path(__file__).resolve().parents[2] / "native" / "generic.cpp").read_text(
            encoding="utf-8", errors="replace"
        )

    def test_unscoped_cut_keeps_the_global_body(self):
        self.assertIn("integer(b, PRO_E_BODY_USE, PRO_BODY_USE_ALL);", self.source)

    def test_scoped_cut_selects_the_requested_body(self):
        self.assertIn("integer(b, PRO_E_BODY_USE, PRO_BODY_USE_SELECTED);", self.source)
        self.assertIn("PRO_E_BODY_SELECT", self.source)
        self.assertIn("require_scopable_body(target)", self.source)

    def test_applied_scope_is_read_from_the_feature_tree(self):
        self.assertIn("scope_applied_report", self.source)
        self.assertIn('{"source", "feature_tree"}', self.source)
        self.assertIn("ProElementReferenceGet", self.source)
        self.assertIn("ProReferenceIdGet", self.source)

    def test_non_target_change_aborts_the_cut(self):
        self.assertIn("F08_SCOPE_NON_TARGET_CHANGED", self.source)
        self.assertIn("non_target_bodies_unchanged", self.source)
        self.assertIn("stage_operation_result(staged)", self.source)

    def test_unresolved_body_is_a_structured_failure(self):
        self.assertIn("F08_SCOPE_RESOLVE_FAILED", self.source)

    def test_a_scope_the_feature_does_not_carry_fails_the_job(self):
        # Readback is evidence: an element that reads as "all bodies", a
        # different id, an unreadable reference or a same-numbered reference of
        # another kind must not report success.
        self.assertIn('applied["applied_body_ids"] == op.at("scope").at("body_ids")', self.source)
        self.assertIn('applied["query_code"] == PRO_TK_NO_ERROR', self.source)
        self.assertIn("if (!resolved)", self.source)
        self.assertIn("feature_tree_unreadable", self.source)
        self.assertIn("use != PRO_BODY_USE_SELECTED", self.source)
        self.assertIn("type != PRO_BODY", self.source)

    def test_an_unreadable_element_keeps_its_query_code(self):
        # get_path throws on a missing element; the receipt must record that
        # code instead of escaping without evidence.
        self.assertIn('report["query_code"] = code;', self.source)
        self.assertIn("catch (ProError missing)", self.source)

    def test_a_half_known_fingerprint_is_unknown_not_equal(self):
        self.assertIn("!was_surfaces.is_number()", self.source)
        self.assertIn("!now_surfaces.is_number()", self.source)
        self.assertIn("!was_bbox.is_array()", self.source)
        self.assertIn("!now_bbox.is_array()", self.source)
        self.assertIn("unknown ? J(nullptr) : J(true)", self.source)
        self.assertIn("!before.contains(it.key())", self.source)

    def test_creo_extrude_forwards_the_scope_into_the_operation(self):
        from pathlib import Path

        source = (Path(__file__).resolve().parents[2] / "server.py").read_text(
            encoding="utf-8", errors="replace"
        )
        self.assertIn('op["scope"] = scope', source)

    def test_compact_and_capabilities_publish_the_scope_evidence(self):
        from creo_mechdog import capabilities, compact_sections

        self.assertIn("scope_applied", compact_sections.OPERATION_KEYS)
        self.assertIn("scope_rejection", compact_sections.OPERATION_KEYS)
        ids = {entry["id"] for entry in capabilities.KNOWN_LIMITATIONS}
        self.assertIn("cut_scope", ids)


if __name__ == "__main__":
    unittest.main()
