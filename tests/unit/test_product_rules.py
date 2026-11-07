"""Offline product rules behavior and rejection regressions."""

import copy
import hashlib
import json
import socket
import subprocess
import unittest
from pathlib import Path
from unittest.mock import patch

from creo_mechdog import product_rules
from creo_mechdog.paths import SOURCE_PATHS
from creo_mechdog.schema import validate_operations

CAPABILITIES = {"operations": ["sketch", "extrude"]}


class ProductRulesTests(unittest.TestCase):
    def build(self, parameters=None, capabilities=CAPABILITIES):
        return product_rules.build_product_plan("box_frame", parameters or {}, capabilities)

    def test_default_and_second_size_schema_geometry_direction(self):
        for parameters, dimensions, volume in [
            ({}, (100, 60, 40, 2), 35712),
            (
                {"length_mm": 120, "width_mm": 80, "height_mm": 50, "wall_mm": 3},
                (120, 80, 50, 3),
                83508,
            ),
        ]:
            with self.subTest(parameters=parameters):
                result = self.build(parameters)
                length, width, height, wall = dimensions
                # Independent sum of bottom plate and four nonoverlapping walls.
                oracle = length * width * wall + (
                    2 * length * wall + 2 * (width - 2 * wall) * wall
                ) * (height - wall)
                self.assertEqual(oracle, volume)
                self.assertEqual(result["expected_geometry"]["volume_mm3"], oracle)
                self.assertEqual(
                    result["expected_geometry"]["bbox_mm"],
                    {"min": [0, 0, 0], "max": [length, width, height]},
                )
                operations = result["plan"]["operations"]
                self.assertEqual(operations, validate_operations(operations))
                self.assertEqual(
                    [op["label"] for op in operations],
                    ["outer_profile", "outer_body", "cavity_profile", "cavity_cut"],
                )
                for index in (0, 2):
                    self.assertEqual(operations[index]["plane"], "XY")
                    self.assertEqual(operations[index]["dimensioning"], "coordinates")
                self.assertEqual(operations[0]["offset"], 0)
                self.assertEqual(operations[0]["entities"][0]["max"], [length, width])
                self.assertEqual(operations[1]["direction"], "positive")
                self.assertEqual(operations[1]["depth"], height)
                self.assertEqual(operations[2]["offset"], height)
                self.assertEqual(operations[2]["entities"][0]["min"], [wall, wall])
                self.assertEqual(operations[2]["entities"][0]["max"], [length - wall, width - wall])
                self.assertEqual(operations[3]["direction"], "negative")
                self.assertEqual(operations[3]["mode"], "cut")
                self.assertEqual(operations[3]["depth"], height - wall)
                self.assertTrue(result["executable"])
                self.assertEqual(
                    result["validation"],
                    {"schema": "passed", "native": "not_run", "saved_reload": "not_run"},
                )

    def test_parameter_boundaries(self):
        for name in ("length_mm", "width_mm", "height_mm"):
            for value in (10, 1000):
                self.assertTrue(self.build({name: value})["executable"])
        for value in (0.5, 20):
            self.assertTrue(self.build({"wall_mm": value})["executable"])
        self.assertTrue(self.build({"length_mm": 10, "wall_mm": 4.5})["executable"])

    def test_reject_invalid_parameters_before_generating_plan(self):
        invalid = [
            {"extra": 1},
            [],
            None,
            {"wall_mm": 0.49},
            {"wall_mm": 20.01},
            {"length_mm": 9.99},
            {"width_mm": 1001},
            {"length_mm": 10, "wall_mm": 4.51},
            {"width_mm": 10, "wall_mm": 5},
            {"height_mm": 10, "wall_mm": 10},
        ]
        invalid += [
            {name: value}
            for name in ("length_mm", "width_mm", "height_mm", "wall_mm")
            for value in (True, False, "12", float("nan"), float("inf"), -float("inf"), 10**10000)
        ]
        for parameters in invalid:
            with (
                self.subTest(kind=type(parameters).__name__),
                patch.object(product_rules, "validate_operations") as validator,
            ):
                with self.assertRaises(ValueError):
                    product_rules.build_product_plan("box_frame", parameters, CAPABILITIES)
                validator.assert_not_called()

    def test_id_whitelist_rejects_paths_before_read(self):
        for template_id in ("../box_frame", "box_frame.json", "C:/box_frame", "", None, []):
            with patch.object(Path, "read_bytes", side_effect=AssertionError("read")):
                with self.assertRaisesRegex(ValueError, "template_id"):
                    product_rules.build_product_plan(template_id, {}, CAPABILITIES)

    def test_capability_unknown_missing_and_malformed(self):
        for snapshot in (
            None,
            {},
            {"operations": []},
            {"operations": ["sketch"]},
            {"operations": ["extrude"]},
        ):
            result = self.build(capabilities=snapshot)
            self.assertFalse(result["executable"])
            self.assertIsNone(result["plan"])
            self.assertTrue(result["blocking_items"])
            self.assertTrue(all("code" in item for item in result["blocking_items"]))
        for snapshot in (
            [],
            True,
            {"operations": None},
            {"operations": "sketch"},
            {"operations": [True]},
            {"operations": [1]},
        ):
            with self.assertRaisesRegex(ValueError, "capability_snapshot"):
                self.build(capabilities=snapshot)
        self.assertEqual(
            self.build(),
            self.build(
                capabilities={"operations": ["extrude", "sketch", "future"], "metadata": object()}
            ),
        )

    def test_template_corruption_rejected(self):
        raw = (SOURCE_PATHS.resource_root / "examples/product_rules/box_frame.json").read_bytes()
        template = json.loads(raw)
        mutations = [
            ("schema_version", 2),
            ("schema_version", True),
            ("template_id", "other"),
            ("template_version", "2.0.0"),
            ("units", {"length": "inch", "angle": "deg"}),
            ("recipe", "eval"),
            ("operation_allowlist", ["shell"]),
            ("validation", {"minimum_cavity_mm": True}),
            ("parameters", {}),
        ]
        for field, value in mutations:
            broken = copy.deepcopy(template)
            broken[field] = value
            with patch.object(Path, "read_bytes", return_value=json.dumps(broken).encode()):
                with self.assertRaisesRegex(ValueError, "template"):
                    self.build()
        for field, value in (
            ("minimum", True),
            ("maximum", float("inf")),
            ("default", 1001),
            ("minimum", 2000),
            ("maximum", 10**1000),
        ):
            broken = copy.deepcopy(template)
            broken["parameters"]["length_mm"][field] = value
            with patch.object(Path, "read_bytes", return_value=json.dumps(broken).encode()):
                with self.assertRaisesRegex(ValueError, "template"):
                    self.build()
        for raw in (b"{", b"\xff", b"[]"):
            with patch.object(Path, "read_bytes", return_value=raw):
                with self.assertRaisesRegex(ValueError, "template"):
                    self.build()
        with patch.object(Path, "read_bytes", side_effect=FileNotFoundError("missing")):
            with self.assertRaisesRegex(ValueError, "template"):
                self.build()

    def test_deterministic_digest_input_and_return_isolation(self):
        params = {"wall_mm": 3}
        snapshot = copy.deepcopy(CAPABILITIES)
        before = copy.deepcopy((params, snapshot))
        first = self.build(params, snapshot)
        second = self.build(params, snapshot)
        self.assertEqual(first, second)
        self.assertEqual((params, snapshot), before)
        raw = (SOURCE_PATHS.resource_root / "examples/product_rules/box_frame.json").read_bytes()
        self.assertEqual(first["template_sha256"], hashlib.sha256(raw).hexdigest())
        first["plan"]["operations"][0]["entities"][0]["min"][0] = 999
        first["normalized_parameters"]["wall_mm"] = 999
        self.assertEqual(second, self.build(params, snapshot))

    def test_complete_utf8_budget_never_truncates_operations(self):
        result = self.build()
        self.assertLessEqual(len(json.dumps(result, ensure_ascii=False).encode()), 32768)
        with patch.object(product_rules, "validate_operations", return_value=[{"x": "界" * 12000}]):
            with self.assertRaisesRegex(ValueError, "32768"):
                self.build()

    def test_pure_no_writes_process_network_or_runtime_imports(self):
        with (
            patch.object(Path, "write_text", side_effect=AssertionError("write")),
            patch.object(Path, "write_bytes", side_effect=AssertionError("write")),
            patch.object(subprocess, "Popen", side_effect=AssertionError("process")),
            patch.object(socket, "socket", side_effect=AssertionError("network")),
        ):
            self.assertTrue(self.build()["executable"])
        source = Path(product_rules.__file__).read_text(encoding="utf-8")
        for forbidden in (
            "import bridge",
            "import generic_bridge",
            "import server",
            "eval(",
            "exec(",
        ):
            self.assertNotIn(forbidden, source)
        for field in ("job_id", "model_id", "revision"):
            self.assertNotIn(field, self.build())


if __name__ == "__main__":
    unittest.main()
