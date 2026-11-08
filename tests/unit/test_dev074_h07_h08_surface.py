"""DEV-074 H07/H08: quilt offset counter-evidence and surface-round contract.

H07 (FEAT-039): no standalone quilt offset exists on this SDK. The public
``surface_offset`` is the documented ProThicken thin single-side offset wall,
so the capability text must keep saying so and no ``quilt_offset`` operation
may be registered. H08 (FEAT-055): the surface-edge round is feasible through
``PRO_FEAT_ROUND`` with a two-face reference, but it is only a registered
contract here -- the tool must not appear before it is implemented.
"""

from __future__ import annotations

import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


class QuiltOffsetCounterEvidenceTests(unittest.TestCase):
    def test_capability_says_offset_wall_not_a_standalone_quilt(self):
        from creo_mechdog.capabilities import families

        limits = families()["surface_chain"]["limits"]
        self.assertIn(
            "surface_offset returns the offset wall, not a standalone offset quilt", limits
        )

    def test_no_standalone_quilt_offset_operation_is_registered(self):
        from creo_mechdog.capabilities import REGISTERED_OPERATIONS, UNAVAILABLE_OPERATIONS

        self.assertNotIn("quilt_offset", REGISTERED_OPERATIONS)
        self.assertNotIn("quilt_offset", UNAVAILABLE_OPERATIONS)

    def test_the_native_offset_is_the_documented_thin_protrusion(self):
        native = (ROOT / "native" / "surfaces.cpp").read_text(encoding="utf-8")
        for lock in (
            "PRO_FEAT_PROTRUSION",
            "PRO_USE_SURFS",
            "PRO_E_FEAT_FORM_ALWAYS_THIN, PRO_THIN",
            "PRO_E_STD_USEQLT_QLT",
            "PRO_E_THICKNESS",
            "PRO_E_SRF_OFFS_METHOD, PRO_OFFS_METH_NORMTOSURF",
        ):
            self.assertIn(lock, native)

    def test_surface_trim_offset_stays_refused_before_a_job_exists(self):
        from creo_mechdog.capabilities import require_available

        with self.assertRaises(ValueError) as caught:
            require_available(
                [
                    {
                        "op": "surface_trim",
                        "label": "trimmed",
                        "target": {"kind": "quilt", "id": 3},
                        "tool": {"kind": "quilt", "id": 4},
                        "keep_side": "one",
                        "offset_mm": 5.0,
                    }
                ]
            )
        self.assertIn("offset_mm is not published", str(caught.exception))


class SurfaceRoundContractTests(unittest.TestCase):
    def test_round_accepts_a_two_face_reference(self):
        from creo_mechdog.schema import validate_operations

        operations = validate_operations(
            [
                {
                    "op": "round",
                    "label": "surface_edge",
                    "size": 3.0,
                    "references": [
                        {
                            "surfaces": [
                                {"kind": "surface", "id": 68},
                                {"kind": "surface", "id": 66},
                            ]
                        }
                    ],
                }
            ]
        )
        self.assertEqual(operations[0]["size"], 3.0)
        self.assertEqual(len(operations[0]["references"]), 1)

    def test_round_still_needs_a_reference_and_a_positive_radius(self):
        from creo_mechdog.schema import validate_operations

        for patch in ({"references": []}, {"size": 0.0}):
            with self.subTest(patch=patch):
                with self.assertRaises(ValueError):
                    validate_operations(
                        [
                            {
                                "op": "round",
                                "label": "surface_edge",
                                "size": 3.0,
                                "references": [
                                    {
                                        "surfaces": [
                                            {"kind": "surface", "id": 68},
                                            {"kind": "surface", "id": 66},
                                        ]
                                    }
                                ],
                                **patch,
                            }
                        ]
                    )

    def test_surface_round_is_not_published_before_it_is_implemented(self):
        from creo_mechdog.capabilities import REGISTERED_OPERATIONS, UNAVAILABLE_OPERATIONS

        self.assertNotIn("surface_round", REGISTERED_OPERATIONS)
        self.assertNotIn("surface_round", UNAVAILABLE_OPERATIONS)

    def test_the_native_round_uses_the_documented_face_pair_reference(self):
        native = (ROOT / "native" / "generic.cpp").read_text(encoding="utf-8")
        for lock in (
            "PRO_FEAT_ROUND",
            "PRO_ROUND_REF_SURF_SURF",
            "PRO_E_RNDCH_REFERENCE_SURFACE1",
            "PRO_E_RNDCH_REFERENCE_SURFACE2",
            "PRO_E_RNDCH_ATTACH_TYPE, PRO_ROUND_ATTACHED",
        ):
            self.assertIn(lock, native)


class HandoffEvidenceTests(unittest.TestCase):
    def test_the_handoff_rows_carry_both_verdicts(self):
        handoff = (ROOT / "docs" / "development" / "DEV-074-HANDOFF.md").read_text(encoding="utf-8")
        self.assertIn("H07 / FEAT-039 | **反证完成，门禁保持", handoff)
        self.assertIn("H08 / FEAT-055 | **可行性确认 + 最小契约登记", handoff)

    def test_the_evidence_directory_exists_with_both_reports(self):
        evidence = ROOT / "docs" / "validation" / "dev074-h07-h08-2026-11-08"
        self.assertTrue((evidence / "EVIDENCE.md").is_file())
        self.assertTrue((evidence / "h07_quilt_offset_probe.json").is_file())
        self.assertTrue((evidence / "h08_surface_round_probe.json").is_file())


if __name__ == "__main__":
    unittest.main()
