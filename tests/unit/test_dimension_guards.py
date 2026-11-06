"""FEAT-004 dimension guards: a stale plan must not move a shifted dimension.

The guard has two copies that must agree: ``src/creo_mechdog/dimension_guards.py``
(pure judgement, tested here) and the native executor (reads every target
before writing the first value). The native copy is guarded by a source check.
"""

import unittest
from pathlib import Path

from pydantic import ValidationError

from creo_mechdog.dimension_guards import check_dimension_guard, has_guard, value_tolerance
from creo_mechdog.schema import DimensionsOp, DimensionValue

ROOT = Path(__file__).resolve().parents[2]


def live(**overrides):
    record = {
        "id": 12,
        "value": 25.0,
        "symbol": "d12",
        "relation_driven": False,
        "owner_feature_id": 7,
        "owner_feature_name": "boss_base",
    }
    record.update(overrides)
    return record


class GuardJudgement(unittest.TestCase):
    def test_without_pins_the_edit_passes(self):
        check_dimension_guard(live(), {"id": 12, "value": 30})
        self.assertFalse(has_guard({"id": 12, "value": 30}))

    def test_matching_value_passes_within_tolerance(self):
        check_dimension_guard(live(), {"id": 12, "value": 30, "expected_value": 25.0})
        pinned = 25.0 + value_tolerance(25.0) / 2
        check_dimension_guard(live(), {"id": 12, "value": 30, "expected_value": pinned})

    def test_moved_value_is_refused_with_both_numbers(self):
        with self.assertRaises(ValueError) as error:
            check_dimension_guard(live(), {"id": 12, "value": 30, "expected_value": 20.0})
        message = str(error.exception)
        self.assertIn("Dimension 12", message)
        self.assertIn("expected 20.0", message)
        self.assertIn("current 25.0", message)
        self.assertIn("boss_base", message)

    def test_unknown_value_is_not_treated_as_a_match(self):
        with self.assertRaises(ValueError) as error:
            check_dimension_guard(live(value=None), {"id": 12, "value": 30, "expected_value": 25.0})
        self.assertIn("unknown", str(error.exception))

    def test_symbol_pin(self):
        check_dimension_guard(live(), {"id": 12, "value": 30, "expected_symbol": "d12"})
        with self.assertRaises(ValueError):
            check_dimension_guard(live(), {"id": 12, "value": 30, "expected_symbol": "d99"})
        with self.assertRaises(ValueError):
            check_dimension_guard(
                live(symbol=None), {"id": 12, "value": 30, "expected_symbol": "d12"}
            )

    def test_owner_pin_accepts_id_or_label(self):
        check_dimension_guard(live(), {"id": 12, "value": 30, "expected_owner": 7})
        check_dimension_guard(live(), {"id": 12, "value": 30, "expected_owner": "boss_base"})
        with self.assertRaises(ValueError):
            check_dimension_guard(live(), {"id": 12, "value": 30, "expected_owner": 8})
        with self.assertRaises(ValueError):
            check_dimension_guard(live(), {"id": 12, "value": 30, "expected_owner": "other"})

    def test_unknown_owner_is_refused(self):
        with self.assertRaises(ValueError):
            check_dimension_guard(
                live(owner_feature_id=None, owner_feature_name=None),
                {"id": 12, "value": 30, "expected_owner": 7},
            )

    def test_relation_driven_dimension_is_refused_even_without_pins(self):
        with self.assertRaises(ValueError) as error:
            check_dimension_guard(live(relation_driven=True), {"id": 12, "value": 30})
        self.assertIn("relations", str(error.exception))

    def test_unknown_relation_state_is_not_treated_as_editable(self):
        # relation_driven is null when the query failed; the guard must not
        # invent a pin match out of an unverifiable state.
        check_dimension_guard(live(relation_driven=None), {"id": 12, "value": 30})
        with self.assertRaises(ValueError):
            check_dimension_guard(
                live(relation_driven=None), {"id": 12, "value": 30, "expected_value": 20.0}
            )


class SchemaShape(unittest.TestCase):
    def test_pins_are_optional_and_preserved(self):
        plain = DimensionValue.model_validate({"id": 12, "value": 30})
        self.assertIsNone(plain.expected_value)
        pinned = DimensionValue.model_validate(
            {
                "id": 12,
                "value": 30,
                "expected_value": 25,
                "expected_symbol": "d12",
                "expected_owner": "boss_base",
            }
        )
        self.assertEqual(pinned.expected_value, 25.0)
        self.assertEqual(pinned.expected_owner, "boss_base")

    def test_boolean_numbers_are_rejected(self):
        for payload in (
            {"id": 12, "value": True},
            {"id": 12, "value": 30, "expected_value": True},
            {"id": 12, "value": 30, "expected_owner": True},
        ):
            with self.assertRaises(ValidationError):
                DimensionValue.model_validate(payload)

    def test_blank_owner_and_non_finite_values_are_rejected(self):
        with self.assertRaises(ValidationError):
            DimensionValue.model_validate({"id": 12, "value": 30, "expected_owner": "  "})
        with self.assertRaises(ValidationError):
            DimensionValue.model_validate({"id": 12, "value": float("nan")})
        with self.assertRaises(ValidationError):
            DimensionValue.model_validate({"id": 12, "value": 30, "expected_value": float("inf")})

    def test_unknown_fields_are_still_rejected(self):
        with self.assertRaises(ValidationError):
            DimensionValue.model_validate({"id": 12, "value": 30, "expected_tol": 0.1})

    def test_plan_level_op_keeps_old_payloads_valid(self):
        op = DimensionsOp.model_validate(
            {"op": "set_dimensions", "values": [{"id": 12, "value": 30}]}
        )
        self.assertEqual(op.values[0].value, 30.0)


class NativeContract(unittest.TestCase):
    """The native copy must read every target before writing the first value."""

    def setUp(self):
        source = (ROOT / "native" / "generic.cpp").read_text(encoding="utf-8")
        # clang-format may wrap these initializers, so compare on collapsed
        # whitespace instead of on one exact line.
        self.source = " ".join(source.split())

    def test_guard_runs_before_the_first_write(self):
        guard = self.source.index('check_dimension_targets(targets, op["values"])')
        write = self.source.index("ProDimensionValueSet(&target.dim")
        self.assertLess(guard, write)

    def test_owner_and_symbol_come_from_real_queries(self):
        self.assertIn("ProDimensionOwnerfeatureGet(&target.dim, &owner)", self.source)
        self.assertIn("ProDimensionSymbolGet(&target.dim, symbol)", self.source)

    def test_inspection_reports_owner_and_editability(self):
        self.assertIn(
            '{"owner_feature_id", owner_code == PRO_TK_NO_ERROR ? J(owner.id) : J(nullptr)}',
            self.source,
        )
        self.assertIn(
            '{"editable", relation_code == PRO_TK_NO_ERROR ? J(relation_driven != PRO_B_TRUE)',
            self.source,
        )


if __name__ == "__main__":
    unittest.main()
