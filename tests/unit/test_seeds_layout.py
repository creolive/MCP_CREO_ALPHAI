"""DEV-002: seed compatibility exports and the installer CLI stay usable."""

import hashlib
import importlib
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


class SeedsLayoutTests(unittest.TestCase):
    def setUp(self):
        self.root = Path(self.enterContext(tempfile.TemporaryDirectory()))
        library = self.root / "seed_library"
        (library / "seeds").mkdir(parents=True)
        (self.root / "docs").mkdir()
        payload = b"isolated seed fixture; never loaded by Creo"
        manifest = {
            "seeds": [
                {
                    "name": "fixture",
                    "relative_path": "seeds/fixture.prt.1",
                    "seed_feature_id": 9,
                    "section_count": 2,
                    "interpolation": "straight",
                    "units": "mm",
                    "sha256": hashlib.sha256(payload).hexdigest(),
                }
            ]
        }
        (library / "seeds/fixture.prt.1").write_bytes(payload)
        for path in (self.root / "docs/seed_manifest.json", library / "seed_manifest.json"):
            path.write_text(json.dumps(manifest), encoding="utf-8")
        for path in (self.root / "LICENSE", library / "LICENSE"):
            path.write_text("MIT fixture\n", encoding="utf-8")

    def cli(self, *args):
        code = """
import runpy, sys
from pathlib import Path
import bridge
bridge.ROOT = Path(sys.argv[1])
def forbidden(*args, **kwargs):
    raise AssertionError('CLI reached Toolkit')
bridge.build_native = forbidden
bridge.toolkit_lock = forbidden
script = sys.argv[2]
sys.argv = [script, *sys.argv[3:]]
runpy.run_path(script, run_name='__main__')
"""
        return subprocess.run(
            [sys.executable, "-B", "-c", code, str(self.root), str(ROOT / "seeds.py"), *args],
            cwd=ROOT,
            capture_output=True,
            text=True,
            timeout=20,
        )

    def test_legacy_exports_share_objects(self):
        implementation = importlib.import_module("creo_mechdog.seeds")
        legacy = importlib.import_module("seeds")
        for name in (
            "expected_archive_sha256",
            "manifest",
            "library_directories",
            "manifest_entry_by_digest",
            "list_seeds",
            "select_seed",
            "validate_seed",
            "install_seed_library",
            "_checked_seed",
            "_validate_library",
        ):
            with self.subTest(export=name):
                self.assertIs(getattr(legacy, name), getattr(implementation, name))
        self.assertTrue(callable(implementation.main))

    def test_cli_listing_emits_one_json_object(self):
        result = self.cli()
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(json.loads(result.stdout)["available_count"], 1)
        self.assertFalse((self.root / "seed_registry.json").exists())

    def test_cli_install_directory_uses_fixture_root(self):
        result = self.cli("--install", "--directory", str(self.root / "seed_library"))
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertTrue(json.loads(result.stdout)["installed"])
        registry = json.loads((self.root / "seed_registry.json").read_text())
        self.assertEqual(registry["directories"], [str((self.root / "seed_library").resolve())])

    def test_cli_rejects_directory_and_archive_together(self):
        result = self.cli("--install", "--directory", str(self.root), "--archive-file", "x.zip")
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("Specify directory or archive_file, not both", result.stderr)
        self.assertFalse((self.root / "seed_registry.json").exists())


if __name__ == "__main__":
    unittest.main()
