"""Offline geometry, matrix, and no-live gates for DEV-051 T06."""

import math
import subprocess
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tools"))

import test_tilted_sketch_lifecycle as lifecycle


class TiltedSketchLifecycleTests(unittest.TestCase):
    def test_polygon_has_thirty_closed_independent_lines_and_area(self):
        entities = lifecycle.polygon_entities()
        self.assertEqual(len(entities), 30)
        self.assertEqual(len({item["name"] for item in entities}), 30)
        for index, entity in enumerate(entities):
            self.assertEqual(entity["end"], entities[(index + 1) % 30]["start"])
        shoelace = (
            abs(
                sum(
                    item["start"][0] * item["end"][1] - item["end"][0] * item["start"][1]
                    for item in entities
                )
            )
            / 2
        )
        self.assertAlmostEqual(shoelace, lifecycle.independent_area_mm2(), places=10)
        self.assertLess(lifecycle.independent_area_mm2(), math.pi * 25)

    def test_case_matrix_is_independent_and_valid(self):
        cases = lifecycle.build_cases("abc12345")
        lifecycle.validate_cases(cases)
        self.assertEqual(len(cases), 32)
        self.assertEqual(len({case["model_name"] for case in cases}), 32)
        for case in cases:
            self.assertTrue(case["new_part_required"])
            self.assertTrue(case["second_reference_must_be_verified_live"])
            self.assertTrue(case["failed_then_same_face_rectangle"]["conditional"])
            kinds = [op["label"] for op in case["ordered_sketch_submissions"]]
            if case["case"].endswith("polygon_then_rectangle"):
                self.assertEqual(kinds, ["polygon", "rectangle"])
            if case["case"].endswith("rectangle_then_polygon"):
                self.assertEqual(kinds, ["rectangle", "polygon"])

    def test_live_gate_refuses_before_creating_report(self):
        result = subprocess.run(
            [sys.executable, str(ROOT / "tools" / "test_tilted_sketch_lifecycle.py"), "--live"],
            cwd=ROOT,
            capture_output=True,
            text=True,
            check=False,
        )
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("refuses --live", result.stderr)


class Bug097StageScannerTests(unittest.TestCase):
    """The four-stage classification of a native.log, per the BUG-097 card."""

    SUCCESS_LOG = (
        "SKETCH_ANCHOR_PLANE=6\n"
        "SECTION_MATRIX_0=0.000000000,1.000000000,0.000000000,0.000000000\n"
        "SECTION_LOCATION_IDENTITY=0 using_location_matrix identity_plausible=0\n"
        "LINE_tri_0=0.000000000,0.000000000 -> 190.382228,22.394433\n"
        "SKETCH_SOLVE=0 mode=coordinates\n"
        "SectionRegenerate=0 mode=coordinates\n"
        "CompleteFeature=0\n"
    )

    L2_FAILURE_LOG = (
        "SKETCH_ANCHOR_PLANE=2\n"
        "SECTION_MATRIX_0=1.000000000,0.000000000,0.000000000,0.000000000\n"
        "SECTION_LOCATION_IDENTITY=1 using_frame_basis identity_plausible=0\n"
        "LINE_tri_0=0.000000000,0.000000000 -> 190.382228,22.394433\n"
        "SKETCH_SOLVE=0 mode=coordinates\n"
        "SectionRegenerate=0 mode=coordinates\n"
        "feature_error element=2889 type=12590 error=-1\n"
        "feature_error element=2890 type=12591 error=5\n"
        "CompleteFeature=-1\n"
    )

    def test_success_path_reaches_all_four_stages_without_failure(self):
        scan = lifecycle.scan_native_log_stages(self.SUCCESS_LOG)
        self.assertEqual(scan["failure_stage"], None)
        for stage in ("frame_validation", "uv_write", "section_regenerate", "complete_feature"):
            self.assertTrue(scan["stages"][stage]["reached"], stage)
            self.assertFalse(scan["stages"][stage]["failed"], stage)
        self.assertFalse(scan["section_location_identity"])
        self.assertFalse(scan["frame_basis_fallback"])

    def test_l2_failure_is_located_to_complete_feature_with_error_entries(self):
        scan = lifecycle.scan_native_log_stages(self.L2_FAILURE_LOG)
        self.assertEqual(scan["failure_stage"], "complete_feature")
        self.assertTrue(scan["section_location_identity"])
        self.assertTrue(scan["frame_basis_fallback"])
        self.assertEqual(scan["feature_error_entries"], 2)
        self.assertTrue(scan["stages"]["section_regenerate"]["reached"])
        self.assertFalse(scan["stages"]["section_regenerate"]["failed"])

    def test_section_regenerate_failure_is_not_misreported_as_complete_feature(self):
        log = self.SUCCESS_LOG.replace("SectionRegenerate=0", "SectionRegenerate=-1").replace(
            "CompleteFeature=0", ""
        )
        scan = lifecycle.scan_native_log_stages(log)
        self.assertEqual(scan["failure_stage"], "section_regenerate")

    def test_frame_validation_refusal_is_the_deepest_reported_stage(self):
        scan = lifecycle.scan_native_log_stages(
            "Sketch u_axis is parallel to the support plane normal"
        )
        self.assertEqual(scan["failure_stage"], "frame_validation")
        self.assertTrue(scan["stages"]["frame_validation"]["failed"])
        for stage in ("uv_write", "section_regenerate", "complete_feature"):
            self.assertFalse(scan["stages"][stage]["reached"], stage)

    def test_empty_log_reports_nothing_as_reached_or_failed(self):
        scan = lifecycle.scan_native_log_stages("")
        self.assertEqual(scan["failure_stage"], None)
        for stage in scan["stages"].values():
            self.assertFalse(stage["reached"])
            self.assertFalse(stage["failed"])

    def test_unreached_stages_are_never_reported_as_passed(self):
        scan = lifecycle.scan_native_log_stages(self.L2_FAILURE_LOG)
        # complete_feature failed; nothing after it exists to judge.
        self.assertFalse(scan["stages"]["complete_feature"]["reached"] is False)


class Bug097Smoke3ptFixtureTests(unittest.TestCase):
    """The archived smoke_3pt_min_repro case as an offline substitute fixture."""

    def test_operations_carry_the_explicit_three_point_kind(self):
        fixture = lifecycle.smoke_3pt_fixture()
        self.assertEqual(fixture["evidence_class"], "substitute_fixture_not_original_job_replay")
        ops = fixture["operations"]
        self.assertEqual(
            [op["op"] for op in ops],
            ["datum_points", "datum_points", "datum_points", "datum_plane", "sketch", "extrude"],
        )
        plane_ref = ops[3]["reference"]
        self.assertEqual(plane_ref["kind"], "through_points")
        self.assertEqual(plane_ref["points"], ["dpa0", "dpb0", "dpd0"])
        sketch_plane = ops[4]["plane"]
        self.assertEqual(sketch_plane["origin"], lifecycle.SMOKE_3PT_POINTS["dpa0"])
        self.assertEqual(sketch_plane["reference"], {"kind": "datum_feature", "label": "pl00a"})

    def test_depth_keeps_the_original_full_precision(self):
        fixture = lifecycle.smoke_3pt_fixture()
        extrude = fixture["operations"][5]
        self.assertEqual(extrude["depth"], lifecycle.SMOKE_3PT_DEPTH_MM)
        self.assertNotEqual(extrude["depth"], 9.87)
        self.assertEqual(extrude["direction"], "symmetric")

    def test_plane_oracle_reproduces_both_external_evidence_points(self):
        oracle = lifecycle.smoke_3pt_plane_oracle()
        self.assertLessEqual(
            oracle["reported_normal_abs_error"], oracle["reported_normal_tolerance"]
        )
        # Pre-fix defect: treating the placeholder identity as the location
        # matrix writes world XY — the archived native.log values, verbatim.
        self.assertTrue(
            oracle["external_buggy_line_uv_reproduced"],
            [vertex["via_location_matrix_uv"] for vertex in oracle["vertices"]],
        )
        # L1 fix: the frame-basis projection returns the input UV exactly and
        # the world->section->world round trip closes on the real positions.
        self.assertTrue(oracle["frame_basis_returns_input_uv"])
        self.assertLessEqual(oracle["max_round_trip_error_mm"], 1e-9)
        self.assertEqual(oracle["identity_loc_mapping"], "frame_basis")
        # The frame is orthonormal: the input u is orthogonalized against the
        # plane normal (the raw [190.382228,0,0] is not in the plane).
        u, v, n = oracle["u_axis_orthogonalized"], oracle["v_axis"], oracle["normal"]

        def dot(a, b):
            return sum(a[i] * b[i] for i in range(3))

        for axis_a, axis_b in ((u, n), (v, n), (u, v)):
            self.assertAlmostEqual(dot(axis_a, axis_b), 0.0, places=9)
        for axis in (u, v, n):
            self.assertAlmostEqual(dot(axis, axis), 1.0, places=9)

    def test_volume_oracle_is_shoelace_times_depth(self):
        oracle = lifecycle.smoke_3pt_volume_oracle()
        points = lifecycle.SMOKE_3PT_TRIANGLE_UV
        independent = (
            abs(
                points[1][0] * points[2][1]
                - points[2][0] * points[1][1]  # vertex at origin contributes zero
            )
            / 2
        )
        self.assertAlmostEqual(oracle["triangle_area_mm2"], independent, places=9)
        self.assertAlmostEqual(
            oracle["symmetric_volume_mm3"],
            independent * lifecycle.SMOKE_3PT_DEPTH_MM,
            places=9,
        )

    def test_schema_gate_records_the_missing_three_point_contract(self):
        gate = lifecycle.smoke_3pt_schema_gate()
        # Q05 registers FEAT-053; validate the preceding point producers too.
        self.assertTrue(gate["accepted"])
        self.assertIsNone(gate["blocked_pending"])
        self.assertIsNone(gate["reason"])

    def test_offline_report_embeds_the_fixture_and_stage_markers(self):
        report = lifecycle.offline_report("abc12345")
        self.assertIn("bug097_smoke_3pt_fixture", report)
        self.assertIn("bug097_stage_markers", report)
        self.assertEqual(
            set(report["bug097_stage_markers"]),
            {"frame_validation", "uv_write", "section_regenerate", "complete_feature"},
        )


if __name__ == "__main__":
    unittest.main()
