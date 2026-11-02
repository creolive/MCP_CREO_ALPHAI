"""BUG-073 public sketch references normalize digit strings to feature IDs."""

import hashlib
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

import bridge
import generic_bridge as general
import server
from creo_mechdog.schema import validate_operations


class SketchReferenceNormalization(unittest.TestCase):
    def op(self, sketch):
        return validate_operations([{"op": "extrude", "label": "t", "sketch": sketch, "depth": 5}])[
            0
        ]

    def test_integer_numeric_string_and_label_passthrough(self):
        for supplied, expected in [(40, 40), ("40", 40), ("040", 40), ("sk_a", "sk_a")]:
            self.assertEqual(self.op(supplied)["sketch"], expected)

    def test_labels_with_digits_are_not_converted(self):
        self.assertEqual(self.op("sk_40")["sketch"], "sk_40")

    def test_out_of_range_numeric_string_rejected(self):
        for value in ("2147483648", "99999999999999", -1, 2147483648):
            with self.assertRaisesRegex(ValueError, "nonnegative 32-bit"):
                self.op(value)

    def test_all_sketch_fields_normalize(self):
        cases = [
            {"op": "revolve", "label": "t", "sketch": "48", "angle": 90},
            {"op": "set_sketch_dimensions", "sketch": "48", "values": {"d0": 1.0}},
            {
                "op": "sheetmetal_wall",
                "label": "t",
                "sketch": "48",
                "depth": 5,
                "thickness": 1,
            },
            {"op": "surface_fill", "label": "t", "sketch": "48"},
            {"op": "rib", "label": "t", "sketch": "48", "thickness": 2},
        ]
        for case in cases:
            self.assertEqual(validate_operations([case])[0]["sketch"], 48, case["op"])


class SketchQueueTests(unittest.IsolatedAsyncioTestCase):
    async def test_public_tool_and_plan_write_identical_integer_references(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            mid = "b" * 32
            target = root / "models" / mid
            target.mkdir(parents=True)
            model = {
                "model_id": mid,
                "model_name": "fixture",
                "status": "ready",
                "revision": 3,
                "model_type": "part",
                "aliases": {},
                "output_directory": str(target / "output"),
                "part_file": None,
            }
            output = target / "output"
            output.mkdir()
            part = output / "fixture.prt.1"
            part.write_bytes(b"controlled saved baseline fixture")
            model.update(
                part_file=str(part), part_sha256=hashlib.sha256(part.read_bytes()).hexdigest()
            )
            template = root / "creo/Common Files/templates/mmns_part_solid_abs.prt"
            template.parent.mkdir(parents=True)
            template.write_bytes(b"fixture, never loaded by native code")
            with (
                patch.object(bridge, "ROOT", root),
                patch.object(bridge, "JOBS", root / "jobs"),
                patch.object(general, "MODELS", root / "models"),
                patch.object(bridge, "config", return_value={"creo_root": str(root / "creo")}),
                patch.object(general.subprocess, "Popen", return_value=Mock()),
                patch.object(server.startup, "require_ready"),
            ):
                for sketch in (48, "48", "sk_rect"):
                    for tool in ("creo_extrude", "creo_execute_plan"):
                        (target / "model.json").write_text(json.dumps(model), encoding="utf-8")
                        op = {"op": "extrude", "label": "pad", "sketch": sketch, "depth": 5}
                        args = {"model_id": mid, "expected_revision": 3}
                        args.update(
                            {"operations": [op]}
                            if tool == "creo_execute_plan"
                            else {
                                "label": "pad",
                                "sketch": sketch,
                                "depth": 5,
                            }
                        )
                        result = await server.mcp.call_tool(tool, args)
                        self.assertFalse(result.is_error, result)
                        job_id = result.structured_content["job_id"]
                        request = bridge.read_json(root / "jobs" / job_id / "request.json")
                        # Release the channel claim as the runner would
                        # (BUG-100) so the next queued comparison submits.
                        bridge.clear_channel_claim(job_id)
                        expected = 48 if sketch in (48, "48") else "sk_rect"
                        self.assertEqual(request["operations"][0]["sketch"], expected)
