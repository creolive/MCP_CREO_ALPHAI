"""C1/F10: executable contract for a one-step tapered extrusion.

Design-stage gate, mirroring ``test_f08_contract.py`` and ``test_f09_contract.py``.
B6 implementation must import ``creo_mechdog.f10_contract`` as its single source
of truth and replace the "no public signature change" sentinels only after a
real-model volume/geometry check exists.

The falsification class below locks the B6 findings in executable form, so a
later change that quietly turns the report's inference into fact (or into a
capability claim) fails here first.
"""

import inspect
import unittest
from pathlib import Path

from creo_mechdog import capabilities, f10_contract, schema

try:
    import server
except Exception:  # pragma: no cover - surfaced by the sentinel assertions below
    server = None

ROOT = Path(__file__).resolve().parents[2]
NATIVE = ROOT / "native"


def native_source(name):
    return (NATIVE / name).read_text(encoding="utf-8", errors="replace")


class F10ContractShape(unittest.TestCase):
    def test_contract_is_explicitly_design_only(self):
        self.assertEqual(f10_contract.STATUS, "designed_not_implemented")
        self.assertEqual(f10_contract.FIELDS, ("draft_angle", "top_scale"))
        self.assertEqual(f10_contract.ALLOWED_KEYS, f10_contract.FIELDS)
        self.assertIsNone(f10_contract.DEFAULTS["draft_angle"])
        self.assertIsNone(f10_contract.DEFAULTS["top_scale"])

    def test_angle_domain_matches_the_existing_draft_tool(self):
        # One angle domain for both routes: DraftOp.angle is gt=-85, lt=85.
        self.assertEqual(f10_contract.ANGLE_LIMIT_DEG, 85.0)
        self.assertEqual(f10_contract.SUPPORTED_MODES, ("add",))
        self.assertEqual(f10_contract.SUPPORTED_DEPTH_TYPES, ("blind",))
        self.assertEqual(f10_contract.SUPPORTED_DIRECTIONS, ("positive", "negative"))
        self.assertEqual(f10_contract.NEUTRAL_PLANE, "sketch_plane")

    def test_top_scale_is_bounded_and_refuses_the_identity_value(self):
        self.assertGreater(f10_contract.TOP_SCALE_MIN, 0.0)
        # Multiplicatively symmetric bounds: the same 100x range both ways.
        self.assertAlmostEqual(f10_contract.TOP_SCALE_MAX * f10_contract.TOP_SCALE_MIN, 1.0, 12)
        self.assertEqual(f10_contract.TOP_SCALE_ONE, 1.0)
        self.assertIn("circular", f10_contract.TOP_SCALE_PROFILE)
        self.assertLessEqual(
            f10_contract.MIN_MAGNITUDE, 1e-9, "a nonzero guard must not admit 1e-12 deg"
        )

    def test_new_body_stays_allowed_because_the_neutral_plane_does_not_move(self):
        self.assertTrue(f10_contract.NEW_BODY_ALLOWED)

    def test_error_codes_are_unique_and_all_have_bounded_input_free_messages(self):
        codes = f10_contract.ERROR_CODES
        self.assertEqual(len(codes), len(set(codes)))
        for code in codes:
            with self.subTest(code=code):
                message = f10_contract.error_message(code)
                self.assertTrue(message)
                self.assertLessEqual(len(message), f10_contract.MAX_ERROR_MESSAGE_CHARS)
                self.assertNotIn("{", message)
                self.assertNotIn("}", message)
                self.assertNotIn("-5778", message)

    def test_native_error_codes_are_separate_from_submission_rejections(self):
        for code in f10_contract.NATIVE_ERROR_CODES:
            with self.subTest(code=code):
                self.assertIn(code, f10_contract.ERROR_CODES)
                self.assertNotIn(code, f10_contract.SUBMISSION_ERROR_CODES)

    def test_limit_note_fits_the_compact_page(self):
        self.assertLessEqual(len(f10_contract.LIMITATION_NOTE), 160)
        self.assertEqual(f10_contract.LIMITATION_ID, "extrude_taper")
        self.assertIn("creo_draft", f10_contract.LIMITATION_NOTE)
        self.assertIn("per-surface", f10_contract.LIMITATION_NOTE)

    def test_taper_receipt_never_fabricates_the_effective_angle(self):
        self.assertEqual(
            f10_contract.TAPER_RECEIPT_FIELDS,
            (
                "requested_angle_deg",
                "requested_top_scale",
                "effective_angle_deg",
                "angle_source",
                "neutral_plane",
                "taper_direction",
                "volume_delta_mm3",
                "query_code",
            ),
        )
        self.assertEqual(f10_contract.ANGLE_SOURCE_FEATURE_TREE, "feature_tree")
        self.assertEqual(f10_contract.ANGLE_SOURCE_UNAVAILABLE, "unavailable")
        self.assertEqual(f10_contract.TAPER_DIRECTIONS, ("inward", "outward"))
        self.assertIn("taper", f10_contract.COMPACT_RESULT_KEYS)
        self.assertIn("draft_angle", f10_contract.PUBLIC_DOCUMENTATION_TARGETS)


class F10DraftInferenceFalsified(unittest.TestCase):
    """Locks B6's falsification: draft works, but needs per-surface references."""

    def test_draft_is_a_compiled_capability_not_a_missing_feature(self):
        self.assertIn("#include <ProDraft.h>", native_source("generic.cpp"))
        draft = capabilities.families()["draft"]
        self.assertTrue(draft["enabled"])
        self.assertIn("variable", draft["limits"])

    def test_draft_requires_one_reference_per_surface(self):
        draft_op = schema.DraftOp.model_json_schema()["properties"]["surfaces"]
        self.assertEqual(draft_op.get("minItems"), 1)
        self.assertEqual(draft_op.get("maxItems"), 200)
        source = native_source("advanced.cpp")
        start = source.index("static void surface_collection(")
        end = source.index("static J generic_mirror(", start)
        collection = source[start:end]
        # One single-surface instruction per item, and no bulk selector.
        self.assertIn("PRO_SURFCOLL_REF_SINGLE", collection)
        self.assertIn("PRO_SURFCOLL_SINGLE_SURF", collection)
        self.assertIn("PRO_SURFCOLL_SINGLE_SURF, PRO_B_TRUE", collection)

    def test_the_documented_route_is_a_two_step_extrude_then_draft(self):
        route = f10_contract.DRAFT_TOOL_ROUTE
        self.assertEqual(route["tool"], "creo_draft")
        self.assertIn("creo_inspect_model", route["surface_source"])
        self.assertIn("per face", route["requires"])
        self.assertIn("none", route["surface_selector"])

    def test_a_non_uniform_frustum_is_left_to_the_two_section_route(self):
        # 3x3 m -> 1.6x1.2 m narrows by a different angle on each axis, so no
        # single draft_angle or top_scale can express it.
        route = f10_contract.NON_UNIFORM_TAPER_ROUTE
        self.assertEqual(route["status"], "not_designed_here")
        self.assertIn("constant angle", route["requirement"])
        self.assertIn("loft", route["route"])

    def test_a_tapered_extrude_is_not_reachable_today(self):
        # The current extrude element tree writes no draft element, so the F10
        # gap is a missing one-step taper entry, not an unusable draft tool.
        source = native_source("generic.cpp")
        self.assertNotIn("PRO_E_STD_DRAFT_ANGLE1", source)
        self.assertNotIn("PRO_EXT_DRFT", source)
        self.assertIn("static J extrude_or_revolve", source)


class F10BackwardCompatibility(unittest.TestCase):
    def test_omitted_taper_keeps_todays_straight_extrude(self):
        verdict = f10_contract.validate_taper_options({})
        self.assertTrue(verdict["accepted"])
        self.assertTrue(verdict["defaulted"])
        self.assertFalse(verdict["native_validation_required"])
        self.assertEqual(verdict["options"], dict(f10_contract.DEFAULTS))
        self.assertIsNone(verdict["code"])

    def test_explicit_null_means_no_taper_without_claiming_a_change(self):
        verdict = f10_contract.validate_taper_options({"draft_angle": None})
        self.assertTrue(verdict["accepted"])
        self.assertFalse(verdict["defaulted"])
        self.assertFalse(verdict["native_validation_required"])
        self.assertIsNone(verdict["options"]["draft_angle"])

    def test_every_accepted_taper_needs_real_model_validation(self):
        angle = f10_contract.validate_taper_options({"draft_angle": 7.5})
        self.assertTrue(angle["accepted"])
        self.assertTrue(angle["native_validation_required"])
        scale = f10_contract.validate_taper_options({"top_scale": 0.8})
        self.assertTrue(scale["accepted"])
        self.assertTrue(scale["native_validation_required"])

    def test_values_are_normalized_and_the_payload_is_not_mutated(self):
        payload = {"draft_angle": 7}
        verdict = f10_contract.validate_taper_options(payload)
        self.assertTrue(verdict["accepted"])
        self.assertEqual(verdict["options"]["draft_angle"], 7.0)
        self.assertIsInstance(verdict["options"]["draft_angle"], float)
        self.assertEqual(payload, {"draft_angle": 7})

    def test_no_taper_request_keeps_every_current_extrude_combination(self):
        # A taper gate must not leak onto the straight extrude, cut, symmetric,
        # through-all or thin modes that exist today.
        contexts = (
            {"mode": "cut"},
            {"mode": "surface"},
            {"direction": "symmetric"},
            {"depth_type": "through_all"},
            {"thin": 2.0},
            {"operation": "revolve"},
        )
        for context in contexts:
            with self.subTest(context=context):
                verdict = f10_contract.validate_taper_options({}, **context)
                self.assertTrue(verdict["accepted"])
                self.assertTrue(verdict["defaulted"])
                self.assertFalse(verdict["native_validation_required"])

    def test_boundary_values_are_accepted(self):
        for angle in (1e-9, -1e-9, 84.999, -84.999, 7.5):
            with self.subTest(angle=angle):
                self.assertTrue(
                    f10_contract.validate_taper_options({"draft_angle": angle})["accepted"]
                )
        for scale in (f10_contract.TOP_SCALE_MIN, f10_contract.TOP_SCALE_MAX, 0.7367, 2.0):
            with self.subTest(scale=scale):
                self.assertTrue(
                    f10_contract.validate_taper_options({"top_scale": scale})["accepted"]
                )

    def test_top_scale_angle_matches_the_draft_angle_domain(self):
        # tan(a) = r(1-s)/h: a scale of 0.5 on r=10/h=10 is 26.5650 deg.
        self.assertAlmostEqual(f10_contract.implied_angle_deg(10.0, 10.0, 0.5), 26.565051, 6)
        # Outward scaling gives the mirror-image negative angle.
        self.assertAlmostEqual(f10_contract.implied_angle_deg(10.0, 10.0, 2.0), -45.0, 9)
        # A scale that implies more than 85 deg must be refused like a wide angle.
        self.assertGreater(abs(f10_contract.implied_angle_deg(100.0, 1.0, 0.01)), 85.0)
        wide = f10_contract.validate_taper_options(
            {"top_scale": 0.01}, radius_mm=100.0, depth_mm=1.0
        )
        self.assertFalse(wide["accepted"])
        self.assertEqual(wide["code"], "F10_TAPER_INVALID_TOP_SCALE")
        inside = f10_contract.validate_taper_options(
            {"top_scale": 0.5}, radius_mm=10.0, depth_mm=10.0
        )
        self.assertTrue(inside["accepted"])
        self.assertAlmostEqual(inside["options"]["top_scale"], 0.5)


class F10StructuredRejections(unittest.TestCase):
    def assert_rejected(self, payload, code, **context):
        verdict = f10_contract.validate_taper_options(payload, **context)
        self.assertFalse(verdict["accepted"])
        self.assertEqual(verdict["code"], code)
        self.assertIsNone(verdict["options"])
        self.assertFalse(verdict["native_validation_required"])
        for code_text in f10_contract.SUBMISSION_ERROR_CODES:
            self.assertNotIn("-5778", f10_contract.error_message(code_text))

    def test_malformed_shapes_and_unknown_keys_are_rejected(self):
        for payload in (None, [], "7.5", {"draft_angle": 5, "extra": 1}):
            with self.subTest(payload=payload):
                self.assert_rejected(payload, "F10_TAPER_INVALID_OPTIONS")

    def test_giving_both_parameters_is_ambiguous(self):
        self.assert_rejected({"draft_angle": 5, "top_scale": 0.9}, "F10_TAPER_AMBIGUOUS_INPUT")

    def test_invalid_angles_are_rejected(self):
        for angle in (0, 0.0, 1e-12, 85, -85, 120, True, "5", float("inf"), float("nan")):
            with self.subTest(angle=angle):
                self.assert_rejected({"draft_angle": angle}, "F10_TAPER_INVALID_ANGLE")

    def test_invalid_scales_are_rejected(self):
        for scale in (
            0,
            0.0,
            -0.5,
            1,
            1.0,
            1 + 1e-12,
            0.009,
            100.0001,
            True,
            "0.8",
            float("nan"),
        ):
            with self.subTest(scale=scale):
                self.assert_rejected({"top_scale": scale}, "F10_TAPER_INVALID_TOP_SCALE")

    def test_unknown_codes_fall_back_to_bounded_guidance(self):
        message = f10_contract.error_message("F10_TAPER_NOT_A_CODE")
        self.assertTrue(message)
        self.assertLessEqual(len(message), f10_contract.MAX_ERROR_MESSAGE_CHARS)
        self.assertIn("extrude_taper", message)

    def test_operations_without_one_neutral_plane_are_rejected(self):
        payload = {"draft_angle": 5}
        contexts = (
            {"mode": "cut"},
            {"mode": "surface"},
            {"direction": "symmetric"},
            {"depth_type": "through_all"},
            {"thin": 2.0},
            {"operation": "revolve"},
        )
        for context in contexts:
            with self.subTest(context=context):
                self.assert_rejected(payload, "F10_TAPER_UNSUPPORTED_OPERATION", **context)

    def test_rejections_never_echo_the_malformed_value(self):
        verdict = f10_contract.validate_taper_options({"draft_angle": 999})
        self.assertFalse(verdict["accepted"])
        self.assertNotIn("999", str(verdict))
        self.assertNotIn("value", verdict)


class F10NoPublicSignatureChange(unittest.TestCase):
    """Sentinels: B6 implementation replaces these with enabled-contract tests."""

    def test_server_import_is_available_for_the_signature_sentinels(self):
        self.assertIsNotNone(server)

    def test_extrude_op_still_has_no_taper_fields(self):
        properties = schema.ExtrudeOp.model_json_schema()["properties"]
        for field in f10_contract.FIELDS:
            self.assertNotIn(field, properties)

    def test_public_extrude_tool_still_has_no_taper_options(self):
        if server is None:  # pragma: no cover
            self.fail("server import unavailable")
        parameters = inspect.signature(server.creo_extrude).parameters
        for field in f10_contract.FIELDS:
            self.assertNotIn(field, parameters)

    def test_existing_draft_tool_semantics_are_untouched(self):
        if server is None:  # pragma: no cover
            self.fail("server import unavailable")
        parameters = list(inspect.signature(server.creo_draft).parameters)
        self.assertEqual(
            parameters,
            [
                "model_id",
                "expected_revision",
                "label",
                "surfaces",
                "neutral_plane",
                "angle",
                "pull_direction",
                "flip",
                "include_tangent",
            ],
        )


if __name__ == "__main__":
    unittest.main()
