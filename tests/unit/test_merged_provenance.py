"""Merged release drivers retain the branch's incomplete-source diagnostics."""

import importlib
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from creo_mechdog import source_provenance


class MergedProvenanceTests(unittest.TestCase):
    def test_release_drivers_share_complete_and_incomplete_source_semantics(self):
        names = (
            "test_arc_direction",
            "test_dev049_profile_replay",
            "test_dev049_tilted_cut",
            "test_installation_loft",
            "test_plan_performance",
            "test_t05_native",
            "test_t07_preview",
            "test_tilted_sketch_lifecycle",
        )
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "server.py").write_text("# distributed source\n", encoding="utf-8")
            for name in names:
                module = importlib.import_module("tools." + name)
                collect = getattr(module, "local_provenance", None) or module.provenance
                with (
                    self.subTest(driver=name),
                    patch.object(module, "ROOT", root),
                    patch.object(source_provenance.shutil, "which", return_value=None),
                    patch.object(source_provenance.subprocess, "run") as process,
                ):
                    evidence = collect()
                    process.assert_not_called()
                    self.assertEqual(evidence["source_scope"], "distributed_source")
                    self.assertEqual(evidence["source_status"], "incomplete")
                    self.assertIsNone(evidence["source_fingerprint"])
                    self.assertTrue(evidence["source_errors"])
                    self.assertEqual(evidence["source_file_count"], 1)
                    self.assertTrue(evidence["git_unavailable"])
                    self.assertIsNone(evidence["dirty"])


if __name__ == "__main__":
    unittest.main()
