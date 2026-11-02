"""Geometry invariants and failures that must be rejected before native mutation."""

import shutil
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import bridge
from creo_mechdog import seeds

ROOT = Path(__file__).resolve().parents[1]


class PortableModeling(unittest.TestCase):
    def test_packaged_seed_choice_needs_no_native_id(self):
        self.assertEqual(seeds.list_seeds()["available_count"], 9)
        selected = seeds.select_seed(5, "smooth")
        self.assertEqual(selected["name"], "five_smooth")
        self.assertTrue(Path(selected["seed_file"]).is_file())
        for count in (3, 4, 6):
            for mode in ("straight", "smooth"):
                self.assertTrue(Path(seeds.select_seed(count, mode)["seed_file"]).is_file())
        with self.assertRaises(ValueError):
            seeds.select_seed(5, "straight")

    def test_relocated_library_and_corrupt_seed_detection(self):
        (ROOT / ".tmp").mkdir(exist_ok=True)
        with tempfile.TemporaryDirectory(dir=ROOT / ".tmp") as directory:
            root = Path(directory).resolve()
            self.assertTrue(root.is_relative_to(ROOT.resolve()))
            shutil.copytree(ROOT / "seed_library", root / "seed_library")
            (root / "docs").mkdir()
            shutil.copy2(ROOT / "docs/seed_manifest.json", root / "docs/seed_manifest.json")
            shutil.copy2(ROOT / "LICENSE", root / "LICENSE")
            with (
                patch.object(bridge, "ROOT", root),
                patch.object(bridge, "config", return_value={}),
            ):
                result = seeds.install_seed_library()
                self.assertEqual(result["available_count"], 9)
                selected = seeds.select_seed(5, "smooth")
                self.assertTrue(Path(selected["seed_file"]).is_relative_to(root))
                Path(selected["seed_file"]).write_bytes(b"corrupt seed")
                self.assertFalse(seeds.validate_seed("five_smooth")["available"])
                with self.assertRaises(ValueError):
                    seeds.select_seed(5, "smooth")

    def test_seed_path_traversal_rejected(self):
        entry = {**seeds.manifest()["seeds"][0], "relative_path": "../outside.prt.1"}
        with self.assertRaises(ValueError):
            seeds._checked_seed(ROOT, entry)


if __name__ == "__main__":
    unittest.main()
