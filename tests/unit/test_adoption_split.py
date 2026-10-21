"""BUG-076: control metadata split from full inspection payloads.

In-process checks for the reference discipline: full payloads move into
content-addressed sidecars, control records keep only a summary plus the
controlled reference, oversized payloads no longer break the read budget, and
tampered/missing references are refused. Legacy inline records keep working.
"""

import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import bridge
import generic_bridge as general
from creo_mechdog import adoption, inspection_refs

INSPECTION = {
    "healthy": True,
    "features": [],
    "surfaces": [],
    "edges": [],
    "bodies": [],
    "datum_planes": [],
    "parameters": {},
    "volume_mm3": 10,
    "units": "mm",
    "units_query_code": 0,
    "model_type": "part",
}


def _write(file: Path, value: dict) -> None:
    file.parent.mkdir(parents=True, exist_ok=True)
    file.write_text(json.dumps(value), encoding="utf-8")


class Split(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory(prefix="bug076_split_")
        self.root = Path(self.temporary.name)
        (self.root / "jobs").mkdir()
        (self.root / "models").mkdir()
        self.root.joinpath("user_parts").mkdir()
        (self.root / "user_parts" / "001.prt").write_bytes(b"fixture user part bytes 001")
        _write(
            self.root / "config.json",
            {"creo_root": "C:\\bug076-fixture-creo", "vcvars64": "C:\\bug076-vcvars64.bat"},
        )
        # Every directory these tests write lives under the patched service
        # root; reference loading rejects paths outside it.
        for patcher in (
            patch.object(bridge, "ROOT", self.root),
            patch.object(bridge, "JOBS", self.root / "jobs"),
            patch.object(general, "MODELS", self.root / "models"),
        ):
            patcher.start()
            self.addCleanup(patcher.stop)

    def tearDown(self):
        self.temporary.cleanup()

    def test_make_ref_is_content_addressed_and_idempotent(self):
        directory = self.root / "sidecars"
        first = inspection_refs.make_ref(INSPECTION, directory, "live")
        second = inspection_refs.make_ref(INSPECTION, directory, "live")
        self.assertEqual(first, second)
        self.assertEqual(Path(first["file"]).name, f"inspection-live-{first['sha256'][:16]}.json")
        other = inspection_refs.make_ref({**INSPECTION, "volume_mm3": 11}, directory, "live")
        self.assertNotEqual(other["file"], first["file"])

    def test_split_moves_inline_payload_into_controlled_sidecar(self):
        holder = {"healthy": True, "inspection": INSPECTION}
        inspection_refs.split(holder, self.root / "jobs" / "j1", "live")
        self.assertNotIn("inspection", holder)
        ref = holder["inspection_ref"]
        self.assertEqual(inspection_refs.load_ref(ref), INSPECTION)
        self.assertEqual(holder["inspection_summary"]["volume_mm3"], 10)
        self.assertTrue(Path(ref["file"]).resolve().is_relative_to(self.root.resolve()))

    def test_split_is_a_noop_for_reference_only_holders(self):
        ref = inspection_refs.make_ref(INSPECTION, self.root / "jobs" / "j2", "verified")
        holder = {"inspection_ref": ref}
        inspection_refs.split(holder, self.root / "jobs" / "j2", "verified")
        self.assertEqual(holder["inspection_ref"], ref)
        self.assertEqual(holder["inspection_summary"]["units"], "mm")

    def test_load_ref_refuses_tampered_truncated_and_missing_references(self):
        directory = self.root / "jobs" / "j3"
        ref = inspection_refs.make_ref(INSPECTION, directory, "live")
        tampered = dict(ref)
        Path(tampered["file"]).write_text(json.dumps({**INSPECTION, "volume_mm3": 99}))
        with self.assertRaises(inspection_refs.InspectionRefInvalid):
            inspection_refs.load_ref(tampered)
        truncated = {**ref, "bytes": ref["bytes"] - 1}
        with self.assertRaises(inspection_refs.InspectionRefInvalid):
            inspection_refs.load_ref(truncated)
        missing = {**ref, "file": str(Path(ref["file"]).with_name("absent.json"))}
        with self.assertRaises(inspection_refs.InspectionRefInvalid):
            inspection_refs.load_ref(missing)

    def test_load_ref_refuses_paths_outside_the_service_directory(self):
        with tempfile.TemporaryDirectory(prefix="bug076_outside_") as outside:
            ref = inspection_refs.make_ref(INSPECTION, Path(outside), "live")
            with self.assertRaises(inspection_refs.InspectionRefInvalid):
                inspection_refs.load_ref(ref)

    def test_oversized_payload_flows_through_inspect_without_budget_hit(self):
        # A full inspection whose serialized form exceeds the 16 MiB budget
        # must flow through inspect: only the sidecar holds the payload.
        huge = {**INSPECTION, "features": [{"pad": "x" * 512} for _ in range(40_000)]}
        self.assertGreater(len(json.dumps(huge)), adoption.BUDGET_BYTES)

        def synthetic(directory: Path, manifest: dict) -> dict:
            result = {
                "connected": True,
                "delivery_complete": True,
                "disconnect_code": 0,
                "success": True,
                "live": {
                    "origin": str(self.root / "user_parts" / "001.prt"),
                    "model_type": "part",
                    "healthy": True,
                    "millimeter_units": True,
                    "dependency_free": True,
                    "session_fingerprint": "bug076-fixture-session",
                    "volume_mm3": 10,
                    "inspection": huge,
                },
            }
            bridge.write_json(directory / "native_result.json", result)
            return result

        with (
            patch.object(bridge, "build_native", return_value=self.root / "worker.exe"),
            patch.object(adoption, "_native", side_effect=synthetic),
        ):
            evidence = adoption.inspect()
        self.assertTrue(evidence["available"])
        self.assertIsNone(evidence["reason"])
        token = evidence["evidence_token"]
        record = bridge.read_json(
            (general.MODELS / evidence["model_id"] / "adoption" / f"evidence-{token}.json")
        )
        # The evidence token stays small: summary plus reference only.
        self.assertLess(
            len(json.dumps(record)),
            64 * 1024,
            "evidence token must not inline the full payload",
        )
        self.assertNotIn("inspection", record["live"])
        loaded = inspection_refs.load_ref(record["live"]["inspection_ref"])
        self.assertEqual(loaded["features"], huge["features"])
        registry = bridge.read_json(general.MODELS / evidence["model_id"] / "model.json")
        self.assertNotIn("inspection", registry)

    def test_apply_request_uses_reference_and_legacy_inline_still_works(self):
        # New records send only the reference in the request.
        holder = {
            "inspection_ref": inspection_refs.make_ref(
                INSPECTION, self.root / "jobs" / "j4", "live"
            )
        }
        field = inspection_refs.request_field(holder, "live_inspection")
        self.assertEqual(list(field), ["live_inspection_ref"])
        # Legacy inline records keep inlining.
        legacy = {"inspection": INSPECTION}
        field = inspection_refs.request_field(legacy, "source_inspection")
        self.assertEqual(list(field), ["source_inspection"])
        # No payload at all is refused explicitly.
        with self.assertRaises(inspection_refs.InspectionRefInvalid):
            inspection_refs.request_field({}, "live_inspection")


if __name__ == "__main__":
    unittest.main()
