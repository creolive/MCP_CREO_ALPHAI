"""Keep the shipped seed manifests tied to the server and packager."""

import ast
import json
import unittest
from pathlib import Path

from creo_mechdog.release_integrity import (
    read_version,
    readme_versions,
    trusted_seed_package,
)
from version import VERSION

ROOT = Path(__file__).resolve().parents[2]


class SeedManifestVersionTests(unittest.TestCase):
    def test_shipped_manifests_match_server_version(self):
        library = json.loads((ROOT / "seed_library/seed_manifest.json").read_text(encoding="utf-8"))
        documentation = json.loads((ROOT / "docs/seed_manifest.json").read_text(encoding="utf-8"))
        self.assertEqual(library, documentation)
        self.assertEqual(library["compatible_server_version"], VERSION)

    def test_packager_checks_manifest_version(self):
        source = (ROOT / "tools/package_seeds.py").read_text(encoding="utf-8")
        tree = ast.parse(source)
        comparisons = [node for node in ast.walk(tree) if isinstance(node, ast.Compare)]
        self.assertTrue(
            any(
                isinstance(compare.left, ast.Subscript)
                and isinstance(compare.left.value, ast.Name)
                and compare.left.value.id == "manifest"
                and isinstance(compare.left.slice, ast.Constant)
                and compare.left.slice.value == "compatible_server_version"
                for compare in comparisons
            ),
            "the packager must compare the manifest version with the source version",
        )

    def test_trusted_seed_package_record_matches_the_server_version(self):
        record = trusted_seed_package(ROOT)
        self.assertEqual(record["compatible_server_version"], VERSION)
        self.assertRegex(record["seed_archive_sha256"], r"^[a-f0-9]{64}$")

    def test_readme_title_and_current_section_match_the_server_version(self):
        readme = readme_versions(ROOT)
        self.assertEqual(readme["title"], VERSION)
        self.assertEqual(readme["current"], VERSION)

    def test_version_module_is_the_single_version_source(self):
        self.assertEqual(read_version(ROOT), VERSION)

    def test_source_package_requires_the_explicit_seed_archive(self):
        source = (ROOT / "tools/package.py").read_text(encoding="utf-8")
        tree = ast.parse(source)
        options = [
            node
            for node in ast.walk(tree)
            if isinstance(node, ast.Call)
            and isinstance(node.func, ast.Attribute)
            and node.func.attr == "add_argument"
            and node.args
            and isinstance(node.args[0], ast.Constant)
            and node.args[0].value == "--seed-archive"
        ]
        self.assertEqual(len(options), 1)
        keywords = {keyword.arg: keyword.value for keyword in options[0].keywords}
        self.assertIn("required", keywords)
        self.assertIs(keywords["required"].value, True)

    def test_source_package_refuses_a_mismatched_seed_archive_before_writing(self):
        source = (ROOT / "tools/package.py").read_text(encoding="utf-8")
        self.assertIn("validate_release_inputs", source)
        self.assertIn("Source package refused", source)
        self.assertLess(
            source.index("validate_release_inputs(ROOT"),
            source.index("zipfile.ZipFile(archive"),
        )


if __name__ == "__main__":
    unittest.main()
