"""B1/F01: seed compatibility preflight must be queryable before any job is submitted."""

import hashlib
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import bridge
import generic_bridge
from creo_mechdog import seeds
from version import VERSION


def _sections(count):
    return [
        {
            "op": "sketch",
            "label": f"s{index}",
            "plane": "XY",
            "offset": float(index * 10),
            "entities": [
                {
                    "type": "polyline",
                    "name": "profile",
                    "points": [[0, 0], [20, 0], [0, 20]],
                    "closed": True,
                }
            ],
        }
        for index in range(count)
    ]


class SeedPreflightContract(unittest.TestCase):
    def setUp(self):
        self.root = Path(self.enterContext(tempfile.TemporaryDirectory()))
        self.enterContext(patch.object(bridge, "ROOT", self.root))
        self.payload = b"#UGC:2 PART 2128 1860 810 1 1 15 4100 2023073 00000285 \\\n#- VERS"
        self.digest = hashlib.sha256(self.payload).hexdigest()
        self.manifest = {
            "compatible_server_version": VERSION,
            "tested_creo": "10.0.0.0",
            "seeds": [
                {
                    "name": "fixture",
                    "relative_path": "seeds/example.prt.1",
                    "seed_feature_id": 9,
                    "section_count": 2,
                    "interpolation": "straight",
                    "units": "mm",
                    "sha256": self.digest,
                }
            ],
        }
        (self.root / "docs").mkdir()
        (self.root / "docs/seed_manifest.json").write_text(
            json.dumps(self.manifest, indent=2), encoding="utf-8"
        )
        library = self.root / "seed_library/seeds"
        library.mkdir(parents=True)
        self.seed_file = library / "example.prt.1"
        self.seed_file.write_bytes(self.payload)

    def test_explicit_seed_section_mismatch_is_rejected_before_submit(self):
        with patch.object(
            generic_bridge, "submit", side_effect=AssertionError("submitted a job")
        ) as submit:
            with self.assertRaises(ValueError) as caught:
                generic_bridge.new_loft_part(
                    str(self.seed_file), 9, _sections(3), interpolation="straight"
                )
            submit.assert_not_called()
        self.assertIn("section", str(caught.exception).lower())

    def test_compatible_creation_returns_a_queryable_preflight_receipt(self):
        with patch.object(
            generic_bridge,
            "submit",
            return_value={"job_id": "job-fixture", "model_id": "model-fixture"},
        ):
            reply = generic_bridge.new_loft_part(
                str(self.seed_file), 9, _sections(2), interpolation="straight"
            )
        preflight = reply["seed_preflight"]
        self.assertEqual(preflight["verdict"], "compatible")
        self.assertTrue(preflight["checked_without_session"])
        self.assertFalse(preflight["callback_required"])
        self.assertIsNone(preflight["session_loadable"])

    def test_list_seeds_advertises_the_callback_free_route(self):
        listed = seeds.list_seeds()
        route = listed["callback_free_route"]
        self.assertEqual(route["tool"], "creo_new_loft_part")
        self.assertFalse(route["callback_required"])
        self.assertIn("creo_list_seeds", route["preflight_tools"])

    def test_preflight_reports_unreadable_bytes_without_session(self):
        from creo_mechdog import seed_preflight

        missing = self.root / "seed_library/seeds/absent.prt.1"
        result = seed_preflight.preflight(2, "straight", str(missing), 9)
        self.assertEqual(result["verdict"], "unverified")
        self.assertTrue(result["checked_without_session"])
        self.assertIsNone(result["session_loadable"])
        self.assertIsNone(result["seed"]["sha256"])
        self.assertIn("could not be read", result["reasons"][0])
