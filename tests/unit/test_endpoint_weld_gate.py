"""BUG-101: publish whether a closed contour can be welded, and why not.

The measured weld threshold comes from the existing native sketch contract:
coordinate dimensioning solves with a 1e-9 mm epsilon while contour closure is
judged at 1e-4 mm. The 2026-10-31 feedback measured 7.83e-13 mm usable and
8.215e-7 mm rejected by the kernel, so 1e-9 is the only published value that
sits between the two observations; this module reports against it and never
invents a value from the request.
"""

import math
import unittest

from creo_mechdog import profile_diagnostics
from creo_mechdog.weldability import weldability_from_report


def report(
    *,
    analysis="complete",
    gaps=(0.0,),
    near=(),
    near_total=None,
    near_truncated=False,
    closed=1,
    open_=0,
):
    """Build the subset of analyze_profile output the weldability gate reads."""
    return {
        "analysis": analysis,
        "closure_tolerance_mm": profile_diagnostics.CLOSURE_TOLERANCE_MM,
        "exact_tolerance_mm": profile_diagnostics.EXACT_TOLERANCE_MM,
        "closed_contour_count": closed,
        "open_contour_count": open_,
        "contours": [{"closed": True, "max_join_gap_mm": gap} for gap in gaps],
        "categories": {
            "near_tolerance": {
                "count": len(near) if near_total is None else near_total,
                "truncated": near_truncated,
                "items": [
                    {"entities": list(entities), "gap_mm": gap, "tolerance_mm": 1e-4}
                    for entities, gap in near
                ],
            }
        },
    }


class WeldabilityThresholdTests(unittest.TestCase):
    def test_gap_below_the_measured_threshold_is_weldable(self):
        result = weldability_from_report(report(gaps=(7.83e-13,)))
        self.assertTrue(result["available"])
        self.assertTrue(result["weldable"])
        self.assertEqual(result["weld_tolerance_mm"], profile_diagnostics.EXACT_TOLERANCE_MM)
        self.assertEqual(result["tolerance_source"], "measured_constant")
        self.assertEqual(result["exceeding_pairs"]["total"], 0)

    def test_gap_above_the_measured_threshold_is_not_weldable(self):
        result = weldability_from_report(
            report(
                gaps=(8.21534262415399e-07,),
                near=(
                    (["gs0_00", "gs0_03"], 8.21534262415399e-07),
                    (["gs0_00", "gs0_01"], 5.60521460071685e-07),
                ),
            )
        )
        self.assertFalse(result["weldable"])
        self.assertEqual(result["max_endpoint_gap_mm"], 8.21534262415399e-07)
        self.assertEqual(result["exceeding_pairs"]["total"], 2)
        self.assertEqual(
            result["exceeding_pairs"]["sample"][0],
            {"entities": ["gs0_00", "gs0_03"], "gap_mm": 8.21534262415399e-07},
        )
        self.assertIn("1e-09", result["note"])

    def test_a_gap_above_the_bound_is_a_risk_flag_not_a_failure_prediction(self):
        # Creo 12.4 extruded an 8.215e-7 mm gap successfully on 2026-11-02, so the
        # report must not tell the caller the feature will fail.
        result = weldability_from_report(
            report(gaps=(8.21534262415399e-07,), near=[(["a", "b"], 8.21534262415399e-07)])
        )
        self.assertFalse(result["weldable"])
        self.assertIn("risk flag, not a prediction", result["note"])
        self.assertIn("may still weld", result["note"])
        self.assertEqual(result["guarantee_scope"], "endpoint_risk_flag")

    def test_explicit_tolerance_is_reported_as_a_request(self):
        result = weldability_from_report(
            report(gaps=(8.2e-7,), near=[(["a", "b"], 8.2e-7)]),
            weld_tolerance_mm=1e-6,
        )
        self.assertTrue(result["weldable"])
        self.assertEqual(result["weld_tolerance_mm"], 1e-6)
        self.assertEqual(result["tolerance_source"], "request")
        self.assertEqual(result["exceeding_pairs"]["total"], 0)

    def test_invalid_explicit_tolerance_is_rejected(self):
        for value in (0, -1.0, float("nan"), float("inf"), True, "1e-9"):
            with self.subTest(value=value), self.assertRaises(ValueError):
                weldability_from_report(report(), weld_tolerance_mm=value)

    def test_open_contour_is_not_weldable_even_without_near_pairs(self):
        result = weldability_from_report(report(gaps=(0.0,), open_=1, closed=0))
        self.assertFalse(result["weldable"])
        self.assertIn("not closed", result["note"])

    def test_unavailable_report_keeps_weldable_unknown(self):
        result = weldability_from_report({"analysis": "unavailable"})
        self.assertFalse(result["available"])
        self.assertIsNone(result["weldable"])
        self.assertIsNone(result["max_endpoint_gap_mm"])
        self.assertIsNone(result["exceeding_pairs"]["total"])

    def test_partial_analysis_never_claims_weldable(self):
        result = weldability_from_report(report(analysis="partial", gaps=(0.0,)))
        self.assertTrue(result["available"])
        self.assertIsNone(result["weldable"])
        self.assertEqual(result["note"], "analysis partial; weldability not determined")

    def test_sample_stays_bounded_and_keeps_the_population_size(self):
        near = [([f"e{index}", f"e{index + 1}"], 8.2e-7) for index in range(40)]
        result = weldability_from_report(
            report(gaps=(8.2e-7,), near=near, near_total=40, near_truncated=True)
        )
        self.assertEqual(result["exceeding_pairs"]["total"], 40)
        self.assertTrue(result["exceeding_pairs"]["truncated"])
        self.assertEqual(len(result["exceeding_pairs"]["sample"]), 20)

    def test_gap_equalling_the_threshold_is_weldable(self):
        result = weldability_from_report(report(gaps=(profile_diagnostics.EXACT_TOLERANCE_MM,)))
        self.assertTrue(result["weldable"])

    def test_nan_gap_cannot_claim_weldable(self):
        result = weldability_from_report(report(gaps=(math.nan,)))
        self.assertIsNone(result["weldable"])


class RealProfileIntegrationTests(unittest.TestCase):
    """The analyzer and the gate must agree on a real two-edge contour."""

    def contour(self, gap):
        return [
            {"type": "line", "name": "a", "start": [0.0, 0.0], "end": [10.0, 0.0]},
            {"type": "line", "name": "b", "start": [10.0, 0.0], "end": [10.0, 10.0]},
            {"type": "line", "name": "c", "start": [10.0, 10.0], "end": [0.0, 10.0]},
            {"type": "line", "name": "d", "start": [0.0, 10.0], "end": [gap, 0.0]},
        ]

    def test_near_tolerance_contour_reports_not_weldable(self):
        entities = self.contour(8.2e-7)
        analysis = profile_diagnostics.analyze_profile(entities)
        result = weldability_from_report(analysis)
        self.assertEqual(analysis["closed_contour_count"], 1)
        self.assertFalse(result["weldable"])
        self.assertGreaterEqual(result["exceeding_pairs"]["total"], 1)

    def test_exact_contour_reports_weldable(self):
        entities = self.contour(0.0)
        analysis = profile_diagnostics.analyze_profile(entities)
        result = weldability_from_report(analysis)
        self.assertTrue(result["weldable"])
        self.assertEqual(result["exceeding_pairs"]["total"], 0)


class NativeAttributionTests(unittest.TestCase):
    """A closed-looking section must not fall back to 'cause is not determined'."""

    def test_extrude_failure_names_the_cluster_spread_when_no_open_ends(self):
        from pathlib import Path

        source = (Path(__file__).resolve().parents[2] / "native" / "generic.cpp").read_text(
            encoding="utf-8"
        )
        start = source.index("static std::string section_create_failure(")
        end = source.index("static ", start + 1)
        body = source[start:end]
        self.assertIn("max_cluster_spread_mm", body)
        self.assertIn("not necessarily welded by the kernel", body)
        # The undetermined text survives only as the last resort.
        self.assertIn("the cause is not determined", body)


class SketchProjectionTests(unittest.TestCase):
    """The sketch result is where the caller learns this before extruding."""

    def project(self, gap):
        from creo_mechdog import operation_results

        entities = RealProfileIntegrationTests().contour(gap)
        result = {
            "operations": [
                {"op": "sketch", "index": 0, "label": "plate", "succeeded": True},
                {"op": "extrude", "index": 1, "label": "pad", "succeeded": False},
            ]
        }
        inputs = [
            {"op": "sketch", "label": "plate", "entities": entities},
            {"op": "extrude", "label": "pad"},
        ]
        operation_results.annotate_profiles(result, inputs)
        return result["operations"][0]["profile"]

    def test_sketch_profile_carries_the_weldability_block(self):
        profile = self.project(8.2e-7)
        self.assertIn("weldability", profile)
        self.assertFalse(profile["weldability"]["weldable"])
        self.assertEqual(profile["weldability"]["tolerance_source"], "measured_constant")

    def test_exact_sketch_profile_reports_weldable(self):
        profile = self.project(0.0)
        self.assertTrue(profile["weldability"]["weldable"])
