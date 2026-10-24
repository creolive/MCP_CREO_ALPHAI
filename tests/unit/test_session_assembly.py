"""Session assembly inspection contracts; native calls are substituted."""

import tempfile
import time
import unittest
from contextlib import ExitStack
from pathlib import Path
from unittest.mock import patch

import bridge
import generic_bridge as general
from creo_mechdog import session_assembly as inspector
from creo_mechdog.model_queries import decode_cursor, encode_cursor, fingerprint
from tests.unit import test_adoption as fixture

IDENTITY = [[1.0, 0.0, 0.0, 0.0], [0.0, 1.0, 0.0, 0.0], [0.0, 0.0, 1.0, 0.0], [0.0, 0.0, 0.0, 1.0]]
TRANSLATED = [
    [1.0, 0.0, 0.0, 0.0],
    [0.0, 1.0, 0.0, 0.0],
    [0.0, 0.0, 1.0, 0.0],
    [20.0, 0.0, 0.0, 1.0],
]


def component(component_id, path, **fields):
    item = {
        "component_id": component_id,
        "occurrence_path": path,
        "parent_path": path[:-1],
        "depth": len(path) - 1,
        "feature_status": 0,
        "suppressed": False,
        "packaged": False,
        "resolved": True,
        "name": fields.pop("name", "p" + str(component_id)),
        "model_type": fields.pop("model_type", "part"),
        "origin": "",
        "has_saved_origin": True,
        "modified": False,
        "session_model_id": 100 + component_id,
        "is_current": False,
        "transform_to_parent": fields.pop("transform_to_parent", IDENTITY),
        "transform_to_root": fields.pop("transform_to_root", IDENTITY),
        "constraints": fields.pop("constraints", []),
        "query_codes": {"transform": 0, "model": 0, "constraints": -1},
    }
    item.update(fields)
    return item


def synthetic_assembly(directory):
    return {
        "session_fingerprint": "fixture-assembly-session",
        "success": True,
        "assembly": {"name": "wb_tree", "model_type": "assembly", "modified": False},
        "complete": True,
        "truncated": False,
        "incomplete": False,
        "depth_limited": False,
        "components": [
            component(5, [5]),
            component(6, [6], name="wb_tree_sub", model_type="assembly"),
            component(9, [6, 9], transform_to_parent=TRANSLATED, transform_to_root=TRANSLATED),
            component(5, [5], transform_to_parent=IDENTITY),
            component(
                7,
                [7],
                resolved=False,
                name=None,
                model_type=None,
                transform_to_parent=None,
                transform_to_root=None,
            ),
        ],
    }


class SessionAssemblyRules(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory(prefix="session_assembly_")
        self.addCleanup(temporary.cleanup)
        self.directory = fixture.prepare_root(Path(temporary.name))
        stack = ExitStack()
        self.addCleanup(stack.close)
        for obj, name, value in (
            (bridge, "ROOT", self.directory),
            (bridge, "JOBS", self.directory / "jobs"),
            (general, "MODELS", self.directory / "models"),
        ):
            stack.enter_context(patch.object(obj, name, value))
        self.native = stack.enter_context(
            patch.object(inspector, "_probe", side_effect=synthetic_assembly)
        )

    def test_tree_order_occurrences_and_transforms(self):
        result = inspector.inspect_session_assembly("wb_tree")
        self.assertEqual(self.native.call_count, 1)
        self.assertEqual(result["total"], 5)
        self.assertTrue(result["complete"])
        paths = [item["occurrence_path"] for item in result["components"]]
        self.assertEqual(paths, [[5], [6], [6, 9], [5], [7]])
        nested = result["components"][2]
        self.assertEqual(nested["depth"], 1)
        self.assertEqual(nested["transform_to_parent"], TRANSLATED)
        unresolved = result["components"][4]
        self.assertFalse(unresolved["resolved"])
        self.assertIsNone(unresolved["name"])
        self.assertIn("transform_convention", result)
        self.assertIn("last row", result["transform_convention"])
        # repeated instances stay separate entries with the same component id
        self.assertEqual(
            result["components"][0]["component_id"], result["components"][3]["component_id"]
        )

    def test_invalid_name_and_limit_rejected(self):
        for name in ("", " ", "  ", 5, "x" * 257):
            with self.assertRaises(ValueError):
                inspector.inspect_session_assembly(name)
        with self.assertRaises(ValueError):
            inspector.inspect_session_assembly("wb_tree", limit=0)
        with self.assertRaises(ValueError):
            inspector.inspect_session_assembly("wb_tree", limit=51)

    def test_cursor_freezes_snapshot_and_rejects_mismatches(self):
        first = inspector.inspect_session_assembly("wb_tree", limit=2)
        self.assertEqual(len(first["components"]), 2)
        self.assertIsNotNone(first["next_cursor"])
        second = inspector.inspect_session_assembly(
            "wb_tree", limit=50, cursor=first["next_cursor"]
        )
        self.assertEqual(self.native.call_count, 1)
        self.assertEqual([item["component_id"] for item in second["components"]], [9, 5, 7])
        self.assertIsNone(second["next_cursor"])
        with self.assertRaises(ValueError):
            inspector.inspect_session_assembly("other_tree", cursor=first["next_cursor"])
        decoded = decode_cursor(first["next_cursor"])
        decoded["kind"] = "session_models"
        with self.assertRaises(ValueError):
            inspector.inspect_session_assembly("wb_tree", cursor=encode_cursor(decoded))
        decoded = decode_cursor(first["next_cursor"])
        decoded["snapshot"] = "nothex"
        with self.assertRaises(ValueError):
            inspector.inspect_session_assembly("wb_tree", cursor=encode_cursor(decoded))
        decoded = decode_cursor(first["next_cursor"])
        decoded["offset"] = 99
        with self.assertRaises(ValueError):
            inspector.inspect_session_assembly("wb_tree", cursor=encode_cursor(decoded))
        with patch.object(inspector.time, "time", return_value=time.time() + 601):
            with self.assertRaises(ValueError):
                inspector.inspect_session_assembly("wb_tree", cursor=first["next_cursor"])
        with patch.object(inspector, "_selection", return_value="another-selection"):
            with self.assertRaises(ValueError):
                inspector.inspect_session_assembly("wb_tree", cursor=first["next_cursor"])

    def test_page_budget_splits_large_components(self):
        def large_probe(directory):
            payload = synthetic_assembly(directory)
            for index, item in enumerate(payload["components"]):
                item["padding"] = "x" * 12000
            return payload

        with patch.object(inspector, "_probe", side_effect=large_probe):
            first = inspector.inspect_session_assembly("wb_tree", limit=50)
        self.assertEqual(len(first["components"]), 2)
        self.assertIsNotNone(first["next_cursor"])
        self.assertEqual(first["total"], 5)

    def test_busy_and_native_failure_rejected(self):
        with patch.object(bridge, "toolkit_lock", side_effect=bridge.ToolkitBusy("fixture busy")):
            with self.assertRaises(bridge.ToolkitBusy):
                inspector.inspect_session_assembly("wb_tree")
        failing = patch.object(
            inspector, "_probe", side_effect=RuntimeError("SESSION_ASSEMBLY_NOT_FOUND: fixture")
        )
        with failing:
            with self.assertRaises(RuntimeError):
                inspector.inspect_session_assembly("wb_tree")

    def test_unit_fields_incomplete_and_depth_limit_passthrough(self):
        payload = synthetic_assembly(self.directory)
        payload["depth_limited"] = True
        payload["incomplete"] = True
        payload["complete"] = False
        payload["root_visit_code"] = 0
        units = {
            "name": "in",
            "query_code": 0,
            "scale_to_mm": 25.4,
            "scale_to_mm_known": True,
            "scale_query_codes": {"unit": 0, "mm_unit": 0, "conversion": 0},
        }
        payload["components"][0]["units"] = {"component": units, "parent": units}
        payload["components"][0]["transform_to_parent"] = None
        payload["components"][0]["transform_to_parent_raw"] = IDENTITY
        payload["components"][0]["transform_mm_known"] = False
        payload["components"][0]["transform_unknown_reason"] = "unknown_units"
        payload["components"][1]["subassembly_visit_code"] = -1
        with patch.object(inspector, "_probe", side_effect=lambda d: payload):
            result = inspector.inspect_session_assembly("wb_tree")
        self.assertTrue(result["depth_limited"])
        self.assertTrue(result["incomplete"])
        self.assertFalse(result["complete"])
        self.assertEqual(result["root_visit_code"], 0)
        first = result["components"][0]
        self.assertIsNone(first["transform_to_parent"])
        self.assertEqual(first["transform_to_parent_raw"], IDENTITY)
        self.assertEqual(first["units"]["component"]["scale_to_mm"], 25.4)
        self.assertEqual(result["components"][1]["subassembly_visit_code"], -1)
        self.assertIn("millimeters", result["transform_convention"])
        self.assertIn("raw", result["transform_convention"])

    def test_root_visit_code_persists_through_snapshot_and_paging(self):
        payload = synthetic_assembly(self.directory)
        payload["complete"] = False
        payload["incomplete"] = True
        payload["root_visit_code"] = -3
        with patch.object(inspector, "_probe", side_effect=lambda d: payload) as probe:
            first = inspector.inspect_session_assembly("wb_tree", limit=2)
            self.assertEqual(first["root_visit_code"], -3)
            self.assertEqual(probe.call_count, 1)  # initial collection probes once
            second = inspector.inspect_session_assembly("wb_tree", cursor=first["next_cursor"])
            self.assertEqual(second["root_visit_code"], -3)
            self.assertEqual(probe.call_count, 1)  # paging reuses the frozen snapshot

    def test_legacy_snapshot_without_schema_version_rejected_without_probe(self):
        first = inspector.inspect_session_assembly("wb_tree", limit=2)
        job_id = first["snapshot_id"]
        file = bridge.job_path(job_id) / "session_assembly.json"
        snapshot = bridge.read_json(file)
        snapshot.pop("schema_version")  # pre-upgrade snapshot shape (raw only)
        snapshot.pop("root_visit_code")  # unit-aware fields did not exist yet
        snapshot.pop("depth_limited")
        bridge.write_json(file, snapshot, durable=True)
        legacy_cursor = encode_cursor(
            {
                "kind": "session_assembly",
                "snapshot": job_id,
                "offset": 0,
                "fingerprint": fingerprint(snapshot),
                "name": "wb_tree",
            }
        )
        with self.assertRaises(ValueError) as raised:
            inspector.inspect_session_assembly("wb_tree", cursor=legacy_cursor)
        self.assertIn("older service version", str(raised.exception))
        self.assertEqual(self.native.call_count, 1)  # rejection: no new Toolkit probe


if __name__ == "__main__":
    unittest.main()
