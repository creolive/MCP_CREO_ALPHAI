"""DEV-002 helper identity, side effects and source-change detection."""

import asyncio
import importlib
import json
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import generic_bridge
import server
from creo_mechdog import capability_pages, schema
from tools import package

ROOT = Path(__file__).resolve().parents[2]
HELPERS = ("schema", "profile_checks", "airfoil")


class HelperLayoutTests(unittest.TestCase):
    def test_legacy_exports_share_objects_with_package(self):
        for name in HELPERS:
            legacy = importlib.import_module(name)
            implementation = importlib.import_module(f"creo_mechdog.{name}")
            self.assertEqual(Path(legacy.__file__).resolve(), ROOT / f"{name}.py")
            self.assertEqual(
                Path(implementation.__file__).resolve(), ROOT / f"src/creo_mechdog/{name}.py"
            )
            public = {key for key in vars(implementation) if not key.startswith("_")}
            self.assertEqual(set(legacy.__all__), public)
            self.assertTrue(public <= set(dir(legacy)))
            for key in public:
                with self.subTest(module=name, export=key):
                    self.assertIs(getattr(legacy, key), getattr(implementation, key))

    def test_service_and_bridge_share_package_models(self):
        self.assertIs(server.SketchOp, schema.SketchOp)
        self.assertIs(server.AirfoilProfile, schema.AirfoilProfile)
        self.assertIs(generic_bridge.LoftOp, schema.LoftOp)
        self.assertIs(generic_bridge.validate_operations, schema.validate_operations)

    def test_installed_imports_are_independent_of_working_directory_and_order(self):
        code = """
import importlib, json, os, sys
from pathlib import Path
def audit(event, args):
 if event in ('os.mkdir', 'os.remove', 'os.rename'):
  raise AssertionError(('import modified files', event, args))
 if event == 'open':
  path, mode, flags = args
  if isinstance(path, (str, bytes)):
   assert Path(os.fsdecode(path)).name not in ('config.json', 'client-config.json'), path
  assert not flags & (os.O_WRONLY | os.O_RDWR | os.O_CREAT | os.O_TRUNC), args
sys.addaudithook(audit)
names = ('schema', 'profile_checks', 'airfoil')
for name in names:
 order = (name, 'creo_mechdog.' + name)
 if sys.argv[1] == 'package_first': order = order[::-1]
 for item in order: importlib.import_module(item)
 legacy, implementation = [importlib.import_module(item) for item in (name, 'creo_mechdog.' + name)]
 assert all(getattr(legacy, key) is getattr(implementation, key) for key in vars(implementation) if not key.startswith('_'))
print(json.dumps({name: [importlib.import_module(name).__file__,
 importlib.import_module('creo_mechdog.' + name).__file__] for name in names}))
"""
        with tempfile.TemporaryDirectory() as directory:
            for order in ("legacy_first", "package_first"):
                result = subprocess.run(
                    [sys.executable, "-B", "-c", code, order],
                    cwd=directory,
                    capture_output=True,
                    text=True,
                    check=True,
                    timeout=20,
                )
                actual = json.loads(result.stdout)
                for name in HELPERS:
                    self.assertEqual(
                        [Path(path).resolve() for path in actual[name]],
                        [ROOT / f"{name}.py", ROOT / f"src/creo_mechdog/{name}.py"],
                    )
                self.assertEqual(list(Path(directory).iterdir()), [])

    def test_runtime_detects_each_migrated_implementation_change(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            for name in server._SOURCE_NAMES:
                destination = root / name
                destination.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(ROOT / name, destination)
            with patch.object(server, "_CODE_ROOT", root):
                self.assertEqual(server._source_fingerprints(), server._LOADED_FINGERPRINTS)
                names = [f"src/creo_mechdog/{module}.py" for module in HELPERS]
                names.append("native/inspection_units.h")
                names.append("native/assembly_pose.h")
                for name in names:
                    self.assertIn(name, server._SOURCE_NAMES)
                    original = (root / name).read_bytes()
                    (root / name).write_bytes(original + b"\n")
                    # The capabilities snapshot is frozen; drop it so the runtime
                    # section reflects the just-changed source.
                    capability_pages.reset_snapshot()
                    page = asyncio.run(server.creo_capabilities(detail="full", section="runtime"))
                    runtime = {entry["key"]: entry["value"] for entry in page["entries"]}
                    self.assertTrue(runtime["source_changed_since_startup"])
                    self.assertEqual(
                        runtime["source_fingerprints_at_startup"], server._LOADED_FINGERPRINTS
                    )
                    (root / name).write_bytes(original)

    def test_distribution_includes_wrappers_implementations_and_moved_tests(self):
        names = {path.relative_to(ROOT).as_posix() for path in package.source_files()}
        required = {f"{name}.py" for name in HELPERS} | {
            f"src/creo_mechdog/{name}.py" for name in HELPERS
        }
        required |= {
            f"tests/unit/test_{name}.py"
            for name in (
                "general_validation",
                "development_validation",
                "v021_validation",
                "sketch_stability",
                "portable_modeling",
                "helper_layout",
                "profile_checks",
            )
        }
        required |= {
            "native/assembly_pose.h",
            "tests/native/test_assembly_pose.cpp",
            "tests/unit/test_assembly_pose.py",
            "tools/test_assembly_pose.py",
            "tools/test_assembly_matrix.py",
        }
        self.assertTrue(required <= names, required - names)


if __name__ == "__main__":
    unittest.main()
