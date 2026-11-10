"""C1/F09: executable contract for configurable raster previews.

Design-stage gate, mirroring ``test_f08_contract.py``. B5 implementation must
import ``creo_mechdog.f09_contract`` as its single source of truth and replace
the "no public signature change" sentinels only after real-model screenshot
evidence exists. A written preview file is not evidence of a readable image.
"""

import inspect
import unittest

from creo_mechdog import f09_contract, preview, schema

try:
    import server
except Exception:  # pragma: no cover - surfaced by the sentinel assertions below
    server = None


class F09ContractShape(unittest.TestCase):
    def test_contract_is_explicitly_design_only(self):
        self.assertEqual(f09_contract.STATUS, "designed_not_implemented")
        self.assertEqual(f09_contract.FIELDS, ("preview_mode", "view", "fit_all"))
        self.assertEqual(f09_contract.PREVIEW_MODES, ("wireframe", "shaded", "shaded_with_edges"))
        self.assertEqual(f09_contract.VIEWS, ("iso", "front", "top", "right"))
        self.assertEqual(f09_contract.DEFAULTS["view"], "iso")
        self.assertTrue(f09_contract.DEFAULTS["fit_all"])
        self.assertIsNone(f09_contract.DEFAULTS["preview_mode"])
        self.assertEqual(
            f09_contract.OPERATION_SURFACES, ("creo_execute_plan", "creo_export_model")
        )

    def test_unverified_values_are_marked_not_silently_accepted_as_working(self):
        self.assertIn("shaded", f09_contract.NATIVE_VALIDATION_REQUIRED)
        self.assertIn("shaded_with_edges", f09_contract.NATIVE_VALIDATION_REQUIRED)
        for view in ("front", "top", "right"):
            self.assertIn(view, f09_contract.NATIVE_VALIDATION_REQUIRED)
        self.assertNotIn("wireframe", f09_contract.NATIVE_VALIDATION_REQUIRED)
        self.assertNotIn("iso", f09_contract.NATIVE_VALIDATION_REQUIRED)

    def test_error_codes_are_unique_and_all_have_bounded_input_free_messages(self):
        codes = f09_contract.ERROR_CODES
        self.assertEqual(len(codes), len(set(codes)))
        for code in codes:
            with self.subTest(code=code):
                message = f09_contract.error_message(code)
                self.assertTrue(message)
                self.assertLessEqual(len(message), f09_contract.MAX_ERROR_MESSAGE_CHARS)
                self.assertNotIn("{", message)
                self.assertNotIn("}", message)
                self.assertNotIn("-5778", message)

    def test_native_error_codes_are_separate_from_submission_rejections(self):
        self.assertNotIn(
            "F09_PREVIEW_DISPLAY_STYLE_UNAVAILABLE", f09_contract.SUBMISSION_ERROR_CODES
        )
        self.assertIn("F09_PREVIEW_DISPLAY_STYLE_UNAVAILABLE", f09_contract.NATIVE_ERROR_CODES)

    def test_limit_note_fits_the_compact_page(self):
        self.assertLessEqual(len(f09_contract.LIMITATION_NOTE), 160)
        self.assertEqual(f09_contract.LIMITATION_ID, "preview_appearance")
        self.assertIn("screenshot", f09_contract.LIMITATION_NOTE)
        self.assertIn("unverified", f09_contract.LIMITATION_NOTE)

    def test_appearance_receipt_never_claims_readability_by_default(self):
        self.assertEqual(f09_contract.READABILITY_DEFAULT, "unverified")
        self.assertEqual(f09_contract.MODE_SOURCE_UNAVAILABLE, "unavailable")
        self.assertEqual(
            f09_contract.APPEARANCE_RECEIPT_FIELDS,
            (
                "requested_mode",
                "applied_mode",
                "mode_source",
                "requested_view",
                "view_matrix_matches",
                "fit_all_applied",
                "annotations_hidden",
                "readability",
            ),
        )
        self.assertIn("preview_appearance", f09_contract.COMPACT_RESULT_KEYS)
        self.assertIn("preview_mode", f09_contract.PUBLIC_DOCUMENTATION_TARGETS)


class F09BackwardCompatibility(unittest.TestCase):
    def test_omitted_options_keep_todays_fixed_preview_behaviour(self):
        verdict = f09_contract.validate_preview_options({})
        self.assertTrue(verdict["accepted"])
        self.assertTrue(verdict["defaulted"])
        self.assertFalse(verdict["native_validation_required"])
        self.assertEqual(verdict["options"], dict(f09_contract.DEFAULTS))
        self.assertIsNone(verdict["code"])

    def test_current_defaults_are_the_existing_fixed_matrix_and_refit(self):
        # The current native path always applies the isometric matrix and calls
        # ProWindowRefit once; a defaulted request must not change either.
        self.assertEqual(f09_contract.EXISTING_VIEW, "iso")
        self.assertTrue(f09_contract.EXISTING_FIT_ALL)

    def test_explicit_wireframe_iso_is_accepted_without_native_validation(self):
        verdict = f09_contract.validate_preview_options(
            {"preview_mode": "wireframe", "view": "iso", "fit_all": True}
        )
        self.assertTrue(verdict["accepted"])
        self.assertFalse(verdict["defaulted"])
        self.assertFalse(verdict["native_validation_required"])
        self.assertTrue(verdict["options"]["fit_all"])

    def test_disabling_the_refit_requires_native_validation(self):
        # fit_all=false needs a native change and a screenshot comparison, so it
        # must not be reported as a validated, ready-to-use option.
        verdict = f09_contract.validate_preview_options({"fit_all": False})
        self.assertTrue(verdict["accepted"])
        self.assertTrue(verdict["native_validation_required"])
        self.assertFalse(verdict["options"]["fit_all"])

    def test_partial_options_are_not_reported_as_fully_defaulted(self):
        verdict = f09_contract.validate_preview_options({"preview_mode": None})
        self.assertTrue(verdict["accepted"])
        self.assertFalse(verdict["defaulted"])
        self.assertEqual(verdict["options"], dict(f09_contract.DEFAULTS))

    def test_options_are_not_mutated_and_rejection_does_not_echo_values(self):
        options = {"preview_mode": "shaded", "view": "front"}
        verdict = f09_contract.validate_preview_options(options)
        self.assertTrue(verdict["accepted"])
        self.assertTrue(verdict["native_validation_required"])
        self.assertEqual(options, {"preview_mode": "shaded", "view": "front"})
        self.assertNotIn("value", verdict)
        for code in f09_contract.SUBMISSION_ERROR_CODES:
            self.assertNotIn("-5778", f09_contract.error_message(code))


class F09StructuredRejections(unittest.TestCase):
    def assert_rejected(self, payload, code):
        verdict = f09_contract.validate_preview_options(payload)
        self.assertFalse(verdict["accepted"])
        self.assertEqual(verdict["code"], code)
        self.assertIsNone(verdict["options"])
        self.assertFalse(verdict["native_validation_required"])

    def test_malformed_shapes_and_unknown_keys_are_rejected(self):
        for payload in (None, [], "shaded", {"preview_mode": "shaded", "extra": 1}):
            with self.subTest(payload=payload):
                self.assert_rejected(payload, "F09_PREVIEW_INVALID_OPTIONS")

    def test_invalid_enum_and_bool_values_are_rejected(self):
        self.assert_rejected({"preview_mode": "solid"}, "F09_PREVIEW_INVALID_MODE")
        self.assert_rejected({"view": "bottom"}, "F09_PREVIEW_INVALID_VIEW")
        self.assert_rejected({"fit_all": "yes"}, "F09_PREVIEW_INVALID_FIT_ALL")
        self.assert_rejected({"fit_all": 1}, "F09_PREVIEW_INVALID_FIT_ALL")

    def test_preview_mode_none_means_no_display_style_change(self):
        verdict = f09_contract.validate_preview_options({"preview_mode": None})
        self.assertTrue(verdict["accepted"])
        self.assertIsNone(verdict["options"]["preview_mode"])
        self.assertFalse(verdict["native_validation_required"])


class F09NoPublicSignatureChange(unittest.TestCase):
    """Sentinels: B5 implementation replaces these with enabled-contract tests."""

    def test_server_import_is_available_for_the_signature_sentinels(self):
        self.assertIsNotNone(server)

    def test_public_tools_still_have_no_preview_options(self):
        if server is None:  # pragma: no cover
            self.fail("server import unavailable")
        for tool in (server.creo_execute_plan, server.creo_export_model):
            with self.subTest(tool=tool.__name__):
                parameters = inspect.signature(tool).parameters
                for field in f09_contract.FIELDS:
                    self.assertNotIn(field, parameters)

    def test_export_op_still_has_no_preview_fields(self):
        properties = schema.ExportOp.model_json_schema()["properties"]
        for field in f09_contract.FIELDS:
            self.assertNotIn(field, properties)

    def test_preview_projection_still_has_no_appearance_receipt(self):
        projected = preview.apply_preview_projection({})
        for key in ("preview_appearance", "preview_mode", "view", "fit_all"):
            self.assertNotIn(key, projected)


if __name__ == "__main__":
    unittest.main()
