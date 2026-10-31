"""BUG-094: datum_plane reference kind, angle-axis selection and angle/offset contract.

Offline only. The reported failure modes fixed here: an angled plane silently
dropped a nonzero offset, a kindless reference surfaced as a JSON missing-key
error from the executor, and a plane-shaped axis selection could resolve to a
face instead of the intended rotation axis.
"""

import copy
import unittest

import server
from creo_mechdog.references import (
    validate_datum_plane_axis,
    validate_datum_plane_reference_kind,
)
from creo_mechdog.schema import PlaneOp, validate_operations


def plane_op(**overrides) -> dict:
    op = {
        "op": "datum_plane",
        "label": "datum",
        "reference": {"kind": "datum_plane", "axis": "z"},
    }
    op.update(overrides)
    return op


class AngleOffsetContractTests(unittest.TestCase):
    def test_reported_angle_with_nonzero_offset_is_rejected(self):
        # F3 problem 3: angle=54 with offset=-8.65981 previously succeeded and
        # silently dropped the offset.
        op = plane_op(offset=-8.65981, angle=54, axis={"kind": "axis", "id": 83})
        with self.assertRaises(ValueError) as caught:
            validate_operations([op])
        message = str(caught.exception)
        self.assertIn("angle", message)
        self.assertIn("nonzero offset", message)
        self.assertIn("datum_plane", message)

    def test_angle_zero_is_also_the_explicit_angle_mode(self):
        for offset in (-1.0, 5.0):
            with self.subTest(offset=offset), self.assertRaises(ValueError) as caught:
                validate_operations(
                    [plane_op(offset=offset, angle=0, axis={"kind": "axis", "id": 83})]
                )
            self.assertIn("nonzero offset", str(caught.exception))

    def test_rejected_combinations_leave_the_input_untouched(self):
        op = plane_op(offset=-8.65981, angle=54, axis={"kind": "axis", "id": 83})
        original = copy.deepcopy(op)
        with self.assertRaises(ValueError):
            validate_operations([op])
        self.assertEqual(op, original)

    def test_offset_only_angle_only_and_angle_with_zero_offset_still_pass(self):
        offset_only = validate_operations([plane_op(offset=7.5)])[0]
        self.assertEqual(offset_only["offset"], 7.5)
        self.assertNotIn("angle", offset_only)
        angle_only = validate_operations(
            [plane_op(angle=54, axis={"kind": "datum_axis_feature", "label": "rotation_axis"})]
        )[0]
        self.assertEqual(angle_only["angle"], 54)
        self.assertEqual(angle_only["offset"], 0)
        self.assertEqual(
            angle_only["axis"], {"kind": "datum_axis_feature", "label": "rotation_axis"}
        )
        tilted_zero = validate_operations([plane_op(angle=0, axis={"kind": "axis", "id": 83})])[0]
        self.assertEqual(tilted_zero["angle"], 0)

    def test_reported_t05_tilt_setup_still_validates(self):
        # tools/test_t05_native.py tilt_setup: angled plane with a datum axis label.
        op = plane_op(
            reference={"kind": "datum_plane", "axis": "x"},
            angle=54,
            axis={"kind": "datum_axis_feature", "label": "rotation_axis"},
        )
        original = copy.deepcopy(op)
        validated = validate_operations([op])[0]
        self.assertEqual(validated["angle"], 54)
        self.assertEqual(validated["offset"], 0)
        self.assertEqual(validated["axis"]["kind"], "datum_axis_feature")
        self.assertEqual(op, original)

    def test_both_entries_share_the_contract(self):
        # The standalone creo_datum_plane tool builds exactly this dict shape and
        # execute_plan validates the same operations list, so one probe covers the
        # shared admission for both entries.
        tool_shape = {
            "op": "datum_plane",
            "label": "datum",
            "reference": {"kind": "datum_plane", "axis": "z"},
            "offset": -8.65981,
            "angle": 54,
            "axis": {"kind": "axis", "id": 83},
        }
        with self.assertRaises(ValueError):
            validate_operations([tool_shape])
        self.assertIsInstance(
            PlaneOp.model_validate(plane_op(angle=0, axis={"kind": "axis", "id": 83})), PlaneOp
        )
        with self.assertRaises(ValueError):
            PlaneOp.model_validate(plane_op(angle=0))


class ReferenceKindTests(unittest.TestCase):
    def test_missing_kind_is_rejected_with_a_clear_error(self):
        for reference in ({}, {"normal": [0, 0, 1]}, {"axis": "z"}, {"kind": None}, {"kind": ""}):
            with self.subTest(reference=reference), self.assertRaises(ValueError) as caught:
                validate_operations([plane_op(reference=reference)])
            message = str(caught.exception)
            self.assertIn("kind", message)
            self.assertIn("before a job is dispatched", message)
            # Not the executor's JSON missing-key error.
            self.assertNotIn("json.exception", message)

    def test_known_reference_kinds_keep_their_semantics(self):
        for reference in (
            {"kind": "datum_plane", "axis": "z"},
            {"kind": "datum_plane", "normal": [0, 0, 1], "offset": 10},
            {"kind": "datum_plane", "id": 163},
            {"kind": "plane", "id": 9},
            {"kind": "surface", "id": 11},
            {"kind": "datum_feature", "label": "plane_label"},
        ):
            with self.subTest(reference=reference):
                validated = validate_operations([plane_op(reference=reference)])[0]
                self.assertEqual(validated["reference"], reference)

    def test_validate_datum_plane_reference_kind_reports_the_path(self):
        with self.assertRaises(ValueError) as caught:
            validate_datum_plane_reference_kind({}, "operations[0].reference")
        self.assertIn("operations[0].reference:", str(caught.exception))

    def test_missing_kind_error_is_distinguishable_from_other_contract_errors(self):
        messages = []
        for op in (
            plane_op(reference={}),
            plane_op(offset=-8.65981, angle=54, axis={"kind": "axis", "id": 83}),
            plane_op(angle=54, axis={"kind": "plane", "id": 9}),
        ):
            with self.assertRaises(ValueError) as caught:
                validate_operations([op])
            messages.append(str(caught.exception))
        self.assertNotEqual(messages[0], messages[1])
        self.assertNotEqual(messages[1], messages[2])


class AngleAxisSelectionTests(unittest.TestCase):
    def test_angle_requires_an_axis(self):
        for angle in (54, 0, -54):
            with self.subTest(angle=angle), self.assertRaises(ValueError) as caught:
                validate_operations([plane_op(angle=angle)])
            self.assertIn("angle axis", str(caught.exception))

    def test_plane_labels_and_wrong_types_are_not_rotation_axes(self):
        bad_axes = [
            {"kind": "plane", "id": 9},
            {"kind": "datum_plane", "axis": "z"},
            {"kind": "surface", "id": 13},
            # datum_feature resolves to a plane surface natively; it must not
            # become the angle axis here (the alias is axis_pattern-only).
            {"kind": "datum_feature", "label": "axis_label"},
            {"kind": "axis"},
            {"kind": "axis", "id": -1},
            {"kind": "axis", "id": "83"},
            {"kind": "axis", "id": True},
            {"kind": "datum_axis_feature"},
            {"kind": "datum_axis_feature", "label": ""},
            {"kind": "datum_axis_feature", "label": 83},
        ]
        for axis in bad_axes:
            with self.subTest(axis=axis), self.assertRaises(ValueError) as caught:
                validate_operations([plane_op(angle=54, axis=axis)])
            message = str(caught.exception)
            self.assertIn("angle axis", message)
            self.assertIn("datum_axis_feature", message)

    def test_non_dictionary_axis_selections_are_rejected(self):
        # pydantic rejects these as dict_type before the shared axis precheck;
        # both entries still refuse them instead of dispatching a job.
        for axis in ("rotation_axis", [], 83, None):
            with self.subTest(axis=axis), self.assertRaises(ValueError):
                validate_operations([plane_op(angle=54, axis=axis)])

    def test_valid_axis_selections_are_preserved(self):
        for axis in ({"kind": "axis", "id": 83}, {"kind": "datum_axis_feature", "label": "ax1"}):
            with self.subTest(axis=axis):
                validated = validate_operations([plane_op(angle=-54, axis=axis)])[0]
                self.assertEqual(validated["axis"], axis)

    def test_validate_datum_plane_axis_reports_the_path(self):
        with self.assertRaises(ValueError) as caught:
            validate_datum_plane_axis({"kind": "plane", "id": 9}, "operations[0].axis")
        self.assertIn("operations[0].axis:", str(caught.exception))


class ToolDescriptionContractTests(unittest.IsolatedAsyncioTestCase):
    async def test_datum_plane_description_states_the_new_contract(self):
        tools = {tool.name: tool for tool in await server.mcp.list_tools()}
        description = " ".join(tools["creo_datum_plane"].description.split())
        self.assertIn("angle (including 0)", description)
        self.assertIn(
            "combining angle with a nonzero offset is rejected before a job is dispatched",
            description,
        )
        self.assertIn("silently dropping the offset", description)
        self.assertIn("{kind:'axis',id:N}", description)
        self.assertIn("{kind:'datum_axis_feature',label:'axis_label'}", description)
        self.assertIn("not a rotation axis", description)
        # P05 wording stays in place and testable.
        self.assertIn(
            "Missing kind and unknown labels are rejected before a job is dispatched",
            description,
        )
        self.assertIn("matches an existing planar face", description)


if __name__ == "__main__":
    unittest.main()
