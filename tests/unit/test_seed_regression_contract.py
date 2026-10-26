import json
import math
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

from creo_mechdog import inspection_refs
from tools.test_feedback037_modeling import seeds
from tools.test_installation_loft import native_result_details, seed_cases


class SeedRegressionContract(unittest.IsolatedAsyncioTestCase):
    def test_inline_result_and_missing_details(self):
        inspection = {"healthy": True, "features": [{"id": 60}], "volume_mm3": 7000}
        aliases = {"blend": {"feature_id": 60}}
        self.assertEqual(
            native_result_details({"result": {"inspection": inspection, "aliases": aliases}}),
            (inspection, aliases),
        )
        with self.assertRaisesRegex(AssertionError, "inspection"):
            native_result_details({"result": {"inspection_summary": {"healthy": True}}})

    def test_controlled_references_and_tampered_file(self):
        inspection = {"healthy": True, "features": [{"id": 60}], "volume_mm3": 7000}
        aliases = {"blend": {"feature_id": 60}}
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            with patch("bridge.ROOT", root):
                ref = inspection_refs.make_ref(inspection, root, "native")
                alias_ref = inspection_refs.make_ref(aliases, root, "aliases", prefix="detail")
                job = {"result": {"inspection_ref": ref, "aliases_ref": alias_ref}}
                self.assertEqual(native_result_details(job), (inspection, aliases))
                Path(ref["file"]).write_bytes(b"changed")
                with self.assertRaises(inspection_refs.InspectionRefInvalid):
                    native_result_details(job)

    async def test_seed_smoke_accepts_summary_and_legacy_inline(self):
        job_ids = ["a" * 32, "b" * 32]
        for field in ("inspection_summary", "inspection"):
            jobs = [
                {
                    "job_id": job_id,
                    "result": {
                        field: {"volume_mm3": 4900 * math.pi / 3},
                        "seed_load_evidence": {
                            "status": "loaded",
                            "evidence_persisted": True,
                            "creo_release_numeric": 44,
                        },
                    },
                }
                for job_id in job_ids
            ]
            validations = [
                {
                    "available": True,
                    "native_compatibility": {
                        "status": "not_verified_for_current_session",
                        "observations": [{"job_id": job_id}],
                    },
                }
                for job_id in job_ids
            ]
            probe = SimpleNamespace(
                job=AsyncMock(side_effect=jobs), call=AsyncMock(side_effect=validations)
            )
            await seeds(probe)
            self.assertEqual(probe.job.await_count, 2)
            self.assertEqual(probe.call.await_count, 2)

    def test_nine_distinct_baselines_and_six_extra_cases(self):
        root = Path(__file__).resolve().parents[2]
        manifest = json.loads((root / "seed_library/seed_manifest.json").read_text("utf-8"))
        cases = seed_cases(manifest)
        names = [name for case, name, _, _ in cases if case.startswith("matrix_")]
        expected = {
            "two_straight",
            "two_smooth",
            "three_straight",
            "three_smooth",
            "four_straight",
            "four_smooth",
            "five_smooth",
            "six_straight",
            "six_smooth",
        }
        self.assertEqual(set(names), expected)
        self.assertEqual(len(names), 9)
        self.assertEqual(len(cases) - len(names), 6)
