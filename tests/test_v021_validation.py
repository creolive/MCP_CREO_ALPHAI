import sys
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from creo_mechdog.capabilities import require_available
from generic_bridge import component_graph, submit


class AdvancedValidation(unittest.TestCase):
    def test_recursive_assembly_cycle_and_busy_source(self):
        with patch("pathlib.Path.is_file", return_value=True):
            f = Path("test_source.asm.1")

            def model(sid, children=()):
                return {
                    "model_id": sid,
                    "status": "ready",
                    "part_file": str(f),
                    "aliases": {str(i): {"source_model_id": c} for i, c in enumerate(children)},
                }

            a = model("a" * 32, ["b" * 32])
            b = model("b" * 32, ["c" * 32])
            c = model("c" * 32)
            db = {v["model_id"]: v for v in (a, b, c)}
            with patch("generic_bridge.model_info", side_effect=db.__getitem__):
                with self.assertRaises(ValueError):
                    component_graph(a, "c" * 32)
                self.assertEqual(len(component_graph(a, "d" * 32)), 3)
                b["pending_job"] = "e" * 32
                with self.assertRaises(ValueError):
                    component_graph(a, "d" * 32)

    def test_unavailable_operations_rejected_before_native_job(self):
        op = {"op": "loft", "label": "transition", "sections": ["first", "second"]}
        with (
            patch.dict(
                "creo_mechdog.capabilities.UNAVAILABLE_OPERATIONS",
                {"loft": "Temporarily disabled for this gate test"},
            ),
            patch("generic_bridge.bridge.toolkit_lock") as lock,
            patch("pathlib.Path.mkdir") as mkdir,
        ):
            with self.assertRaisesRegex(ValueError, "no native job was queued"):
                submit([op])
            lock.assert_not_called()
            mkdir.assert_not_called()
        require_available([{"op": "sheetmetal_flange"}])

    def test_direct_blend_unsupported_material_modes_rejected_before_queue(self):
        base = {"op": "loft", "label": "transition", "sections": ["first", "second"]}
        with (
            patch("generic_bridge.bridge.toolkit_lock") as lock,
            patch("pathlib.Path.mkdir") as mkdir,
        ):
            for fields in ({"mode": "cut"}, {"mode": "surface"}, {"new_body": True}):
                with self.assertRaisesRegex(ValueError, "default body only"):
                    submit([{**base, **fields}])
            lock.assert_not_called()
            mkdir.assert_not_called()


if __name__ == "__main__":
    unittest.main()
