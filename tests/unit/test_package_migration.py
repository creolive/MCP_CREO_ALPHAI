"""DEV-002: installed helpers resolve without the checkout as a working directory."""

import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

import generic_bridge
import server
from creo_mechdog import capabilities, seeds

ROOT = Path(__file__).resolve().parents[2]


class PackageMigrationTests(unittest.TestCase):
    def child(self, code, *args):
        with tempfile.TemporaryDirectory() as directory:
            result = subprocess.run(
                [sys.executable, "-I", "-B", "-c", code, *args],
                cwd=directory,
                capture_output=True,
                text=True,
                timeout=30,
            )
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertEqual(list(Path(directory).iterdir()), [])
            return result.stdout

    def test_external_cwd_imports_resolve_same_checkout(self):
        output = self.child("""
import importlib, json
names = ('bridge', 'seeds', 'capabilities', 'creo_mechdog.seeds', 'creo_mechdog.capabilities')
print(json.dumps({name: importlib.import_module(name).__file__ for name in names}))
""")
        actual = json.loads(output)
        for name, path in actual.items():
            expected = (
                (ROOT / "src" / name.replace(".", "/")).with_suffix(".py")
                if "." in name
                else ROOT / (name + ".py")
            )
            self.assertEqual(Path(path).resolve(), expected)

    def test_legacy_first_and_package_first_imports(self):
        code = """
import importlib, sys
for name in ('seeds', 'capabilities'):
    names = (name, 'creo_mechdog.' + name)
    if sys.argv[1] == 'package_first':
        names = names[::-1]
    for item in names:
        importlib.import_module(item)
    legacy = importlib.import_module(name)
    implementation = importlib.import_module('creo_mechdog.' + name)
    assert set(legacy.__all__) <= set(dir(legacy))
    for key in legacy.__all__:
        assert getattr(legacy, key) is getattr(implementation, key), (name, key)
"""
        for order in ("legacy_first", "package_first"):
            with self.subTest(order=order):
                self.child(code, order)

    def test_pure_import_does_not_read_configuration_or_mutate_files(self):
        self.child("""
import os, sys
from pathlib import Path
def audit(event, args):
    if event in ('os.mkdir', 'os.remove', 'os.rename', 'subprocess.Popen'):
        raise AssertionError(('import side effect', event))
    if event == 'open':
        path, mode, flags = args
        if isinstance(path, (str, bytes)):
            assert Path(os.fsdecode(path)).name not in ('config.json', 'client-config.json')
        assert not flags & (os.O_WRONLY | os.O_RDWR | os.O_CREAT | os.O_TRUNC), args
sys.addaudithook(audit)
import seeds, capabilities
from creo_mechdog import seeds as implementation
assert seeds.list_seeds is implementation.list_seeds
""")

    def test_service_uses_package_implementations(self):
        self.assertIs(server.seeds, seeds)
        self.assertIs(server.families, capabilities.families)
        self.assertIs(generic_bridge.require_available, capabilities.require_available)


if __name__ == "__main__":
    unittest.main()
