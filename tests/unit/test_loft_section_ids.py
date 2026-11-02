"""BUG-028 public section references normalize before duplicate validation."""

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


class LoftSectionIds(unittest.TestCase):
    def op(self, sections):
        return validate_operations([{"op": "loft", "label": "blend", "sections": sections}])[0]

    def test_integer_numeric_string_and_mixed_references(self):
        for supplied, expected in [
            ([40, 49], [40, 49]),
            (["40", "049"], [40, 49]),
            (["sk_a", "sk_b"], ["sk_a", "sk_b"]),
            (["40", "sk_b"], [40, "sk_b"]),
        ]:
            self.assertEqual(self.op(supplied)["sections"], expected)

    def test_normalized_duplicates_rejected(self):
        for supplied in ([40, "40"], ["040", "40"]):
            with self.assertRaisesRegex(ValueError, "distinct"):
                self.op(supplied)

    def test_labels_are_not_globally_converted(self):
        self.assertEqual(self.op(["sk_40", "sk_49"])["sections"], ["sk_40", "sk_49"])

    def test_invalid_native_id_rejected(self):
        for value in (-1, 2147483648, True):
            with self.assertRaises(ValueError):
                self.op([value, "sk_b"])


class LoftQueueTests(unittest.IsolatedAsyncioTestCase):
    async def test_public_tool_and_plan_write_identical_integer_references(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            mid = "a" * 32
            target = root / "models" / mid
            target.mkdir(parents=True)
            model = {
                "model_id": mid,
                "model_name": "fixture",
                "status": "ready",
                "revision": 7,
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
                for sections in ([40, 49], ["40", "49"], [40, "sk_b"]):
                    for tool in ("creo_loft", "creo_execute_plan"):
                        (target / "model.json").write_text(json.dumps(model), encoding="utf-8")
                        op = {"op": "loft", "label": "blend", "sections": sections}
                        args = {"model_id": mid, "expected_revision": 7}
                        args.update(
                            {"operations": [op]}
                            if tool == "creo_execute_plan"
                            else {"label": "blend", "sections": sections}
                        )
                        result = await server.mcp.call_tool(tool, args)
                        self.assertFalse(result.is_error, result)
                        job_id = result.structured_content["job_id"]
                        request = bridge.read_json(root / "jobs" / job_id / "request.json")
                        # Release the channel claim as the runner would
                        # (BUG-100) so the next queued comparison submits.
                        bridge.clear_channel_claim(job_id)
                        expected = [40, "sk_b"] if sections[-1] == "sk_b" else [40, 49]
                        self.assertEqual(request["operations"][0]["sections"], expected)
