"""DEV-048: sidecar integrity, fallback and the published inspection_warnings.

Offline checks only: every directory lives under a temporary root, and file
errors are injected by patching the helper instead of touching Creo or a real
job directory.
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
VERIFIED = {**INSPECTION, "volume_mm3": 11, "features": [{"id": 1, "name": "Extrude"}]}


def _write(file: Path, value: dict) -> None:
    file.parent.mkdir(parents=True, exist_ok=True)
    file.write_text(json.dumps(value), encoding="utf-8")


class Fixture(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory(prefix="dev048_warnings_")
        self.root = Path(self.temporary.name)
        (self.root / "jobs").mkdir()
        (self.root / "models").mkdir()
        self.root.joinpath("user_parts").mkdir()
        self.part = self.root / "user_parts" / "001.prt"
        self.part.write_bytes(b"fixture user part bytes 001")
        _write(
            self.root / "config.json",
            {"creo_root": "C:\\dev048-fixture-creo", "vcvars64": "C:\\dev048-vcvars64.bat"},
        )
        for patcher in (
            patch.object(bridge, "ROOT", self.root),
            patch.object(bridge, "JOBS", self.root / "jobs"),
            patch.object(general, "MODELS", self.root / "models"),
        ):
            patcher.start()
            self.addCleanup(patcher.stop)

    def tearDown(self):
        self.temporary.cleanup()

    def sidecars(self, directory: Path) -> list[str]:
        return sorted(p.name for p in directory.iterdir())


class SidecarIntegrity(Fixture):
    def test_repeating_a_payload_reuses_one_verified_file(self):
        directory = self.root / "jobs" / "reuse"
        first = inspection_refs.make_ref(INSPECTION, directory, "live")
        second = inspection_refs.make_ref(INSPECTION, directory, "live")
        self.assertEqual(first, second)
        self.assertEqual(self.sidecars(directory), [Path(first["file"]).name])
        inspection_refs.verify_ref(first)

    def test_same_size_conflict_keeps_the_other_file_and_republishes(self):
        directory = self.root / "jobs" / "conflict"
        directory.mkdir(parents=True)
        digest = inspection_refs.content_digest(INSPECTION)
        decoy = directory / f"inspection-live-{digest[:16]}.json"
        data = json.dumps(INSPECTION, ensure_ascii=False, indent=2)
        foreign = data.replace('"volume_mm3": 10', '"volume_mm3": 99')
        self.assertEqual(len(foreign.encode()), len(data.encode()))
        decoy.write_text(foreign, encoding="utf-8")
        ref = inspection_refs.make_ref(INSPECTION, directory, "live")
        self.assertEqual(decoy.read_text(encoding="utf-8"), foreign)
        self.assertNotEqual(Path(ref["file"]), decoy)
        self.assertEqual(inspection_refs.load_ref(ref), INSPECTION)
        self.assertEqual(len(self.sidecars(directory)), 2)

    def test_publish_conflict_keeps_names_and_cleans_its_temporary_file(self):
        directory = self.root / "jobs" / "publish"
        directory.mkdir(parents=True)
        digest = inspection_refs.content_digest(INSPECTION)
        (directory / f"inspection-live-{digest[:16]}.json").mkdir()
        (directory / f"inspection-live-{digest}.json").mkdir()
        with self.assertRaises(inspection_refs.SidecarPublishFailed) as caught:
            inspection_refs.make_ref(INSPECTION, directory, "live")
        self.assertEqual(caught.exception.reason_code, "native_sidecar_publish_failed")
        self.assertEqual(len(self.sidecars(directory)), 2)
        self.assertFalse([name for name in self.sidecars(directory) if name.endswith(".tmp")])

    def test_write_failure_is_classified_and_leaves_no_temporary_file(self):
        directory = self.root / "jobs" / "write"
        directory.mkdir(parents=True)
        with patch.object(
            inspection_refs.os, "fsync", side_effect=OSError(28, "no space left on device")
        ):
            with self.assertRaises(inspection_refs.SidecarWriteFailed) as caught:
                inspection_refs.make_ref(INSPECTION, directory, "live")
        self.assertEqual(caught.exception.reason_code, "native_sidecar_write_failed")
        self.assertEqual(self.sidecars(directory), [])

    def test_blocked_directory_is_a_write_failure(self):
        blocked = self.root / "jobs" / "blocked"
        blocked.parent.mkdir(parents=True, exist_ok=True)
        blocked.write_text("not a directory", encoding="utf-8")
        with self.assertRaises(inspection_refs.SidecarWriteFailed):
            inspection_refs.make_ref(INSPECTION, blocked, "live")

    def test_verify_ref_refuses_missing_truncated_and_outside_files(self):
        directory = self.root / "jobs" / "verify"
        ref = inspection_refs.make_ref(INSPECTION, directory, "live")
        inspection_refs.verify_ref(ref)
        missing = {**ref, "file": str(Path(ref["file"]).with_name("absent.json"))}
        with self.assertRaises(inspection_refs.InspectionRefInvalid):
            inspection_refs.verify_ref(missing)
        truncated = {**ref, "bytes": ref["bytes"] - 1}
        with self.assertRaises(inspection_refs.InspectionRefInvalid):
            inspection_refs.verify_ref(truncated)
        with tempfile.TemporaryDirectory(prefix="dev048_outside_") as outside:
            external = inspection_refs.make_ref(INSPECTION, Path(outside), "live")
            with self.assertRaises(inspection_refs.InspectionRefInvalid):
                inspection_refs.verify_ref(external)


class WarningShape(Fixture):
    def test_entries_dedupe_by_stage_and_reason_and_keep_the_newest(self):
        holder = {}
        inspection_refs.add_warning(
            holder,
            stage="live",
            reason_code="native_sidecar_write_failed",
            fallback_status="not_attempted",
            message="first",
        )
        inspection_refs.add_warning(
            holder,
            stage="live",
            reason_code="native_sidecar_write_failed",
            fallback_status="verified",
            message="upgraded",
        )
        entries = inspection_refs.warnings_of(holder)
        self.assertEqual(len(entries), 1)
        self.assertEqual(entries[0]["fallback_status"], "verified")
        self.assertEqual(entries[0]["message"], "upgraded")

    def test_more_than_four_entries_keep_the_newest(self):
        holder = {}
        for index, reason in enumerate(inspection_refs.WARNING_REASONS * 2):
            inspection_refs.add_warning(
                holder,
                stage="live" if index % 2 else "verified",
                reason_code=reason,
                fallback_status="failed",
                message=f"entry {index}",
            )
        entries = inspection_refs.warnings_of(holder)
        self.assertEqual(len(entries), inspection_refs.MAX_WARNINGS)
        self.assertEqual(entries[-1]["message"], "entry 7")

    def test_message_is_bounded_without_splitting_a_character(self):
        holder = {}
        message = "ab\u00e9" * 200
        inspection_refs.add_warning(
            holder,
            stage="verified",
            reason_code="inspection_ref_invalid",
            fallback_status="failed",
            message=message,
        )
        published = holder["inspection_warnings"][0]["message"]
        self.assertLessEqual(len(published.encode("utf-8")), inspection_refs.MAX_MESSAGE_BYTES)
        self.assertTrue(published.endswith("\u2026"))
        published.encode("utf-8").decode("utf-8")  # never a split code point

    def test_unknown_codes_are_refused_and_malformed_entries_ignored(self):
        holder = {"inspection_warnings": [{"stage": "bogus"}, "text", {"stage": "live"}]}
        self.assertEqual(inspection_refs.warnings_of(holder), [])
        with self.assertRaises(ValueError):
            inspection_refs.add_warning(
                holder,
                stage="live",
                reason_code="something_else",
                fallback_status="failed",
                message="x",
            )
        with self.assertRaises(ValueError):
            inspection_refs.add_warning(
                holder,
                stage="live",
                reason_code="inspection_ref_invalid",
                fallback_status="unknown",
                message="x",
            )


class SplitCloseout(Fixture):
    def test_legacy_inline_result_splits_without_a_warning(self):
        directory = self.root / "jobs" / "legacy"
        result = {"success": True, "live": {"origin": "fixture", "inspection": INSPECTION}}
        inspection_refs.split_result(result, directory)
        self.assertNotIn("inspection", result["live"])
        self.assertIn("inspection_ref", result["live"])
        self.assertNotIn("inspection_warnings", result)

    def test_native_failure_is_upgraded_after_the_python_fallback(self):
        directory = self.root / "jobs" / "upgrade"
        result = {
            "live": {"inspection": INSPECTION},
            "inspection_warnings": [
                {
                    "stage": "live",
                    "reason_code": "native_sidecar_write_failed",
                    "fallback_status": "not_attempted",
                    "message": "Cannot write the inspection sidecar file",
                }
            ],
        }
        inspection_refs.split_result(result, directory)
        self.assertNotIn("inspection", result["live"])
        warnings = inspection_refs.warnings_of(result)
        self.assertEqual(len(warnings), 1)
        self.assertEqual(warnings[0]["stage"], "live")
        self.assertEqual(warnings[0]["fallback_status"], "verified")
        self.assertIn("Python fallback was verified", warnings[0]["message"])

    def test_double_failure_keeps_the_inline_payload_and_reports_failed(self):
        directory = self.root / "jobs" / "double"
        result = {
            "success": True,
            "live": {"inspection": INSPECTION},
            "inspection": VERIFIED,
            "inspection_warnings": [
                {
                    "stage": "live",
                    "reason_code": "native_sidecar_write_failed",
                    "fallback_status": "not_attempted",
                    "message": "Cannot write the inspection sidecar file",
                }
            ],
        }
        with patch.object(
            inspection_refs,
            "make_ref",
            side_effect=inspection_refs.SidecarWriteFailed("disk is full"),
        ):
            inspection_refs.split_result(result, directory)
        self.assertIn("inspection", result["live"])
        self.assertIn("inspection", result)
        live = next(w for w in result["inspection_warnings"] if w["stage"] == "live")
        self.assertEqual(live["fallback_status"], "failed")
        self.assertIn("disk is full", live["message"])
        verified = next(w for w in result["inspection_warnings"] if w["stage"] == "verified")
        self.assertEqual(verified["reason_code"], "native_sidecar_write_failed")
        self.assertEqual(verified["fallback_status"], "failed")

    def test_each_stage_closes_independently(self):
        for failing in ("live", "verified"):
            with self.subTest(failing=failing):
                directory = self.root / "jobs" / f"stage_{failing}"
                result = {"live": {"inspection": INSPECTION}, "inspection": VERIFIED}
                original = inspection_refs.make_ref

                def selective(value, path, stem, *, prefix="inspection"):
                    if stem == failing:
                        raise inspection_refs.SidecarPublishFailed("publish blocked")
                    return original(value, path, stem, prefix=prefix)

                with patch.object(inspection_refs, "make_ref", side_effect=selective):
                    inspection_refs.split_result(result, directory)
                warnings = inspection_refs.warnings_of(result)
                self.assertEqual([entry["stage"] for entry in warnings], [failing])
                self.assertEqual(warnings[0]["reason_code"], "native_sidecar_publish_failed")
                self.assertEqual(warnings[0]["fallback_status"], "failed")
                healthy = "verified" if failing == "live" else "live"
                holder = result["live"] if healthy == "live" else result
                self.assertIn("inspection_ref", holder)
                self.assertNotIn("inspection", holder)

    def test_an_unreadable_reference_is_not_published(self):
        directory = self.root / "jobs" / "invalid"
        ref = inspection_refs.make_ref(INSPECTION, directory, "live")
        Path(ref["file"]).write_text(json.dumps({**INSPECTION, "volume_mm3": 99}))
        result = {"live": {"inspection_ref": ref}}
        inspection_refs.split_result(result, directory)
        self.assertNotIn("inspection_ref", result["live"])
        warnings = inspection_refs.warnings_of(result)
        self.assertEqual(warnings[0]["reason_code"], "inspection_ref_invalid")
        self.assertEqual(warnings[0]["fallback_status"], "not_attempted")

    def test_compact_and_full_projection_keep_the_diagnostics(self):
        warning = {
            "stage": "live",
            "reason_code": "native_sidecar_write_failed",
            "fallback_status": "verified",
            "message": "Native sidecar write failed; Python fallback was verified",
        }
        manifest = {
            "job_id": "a" * 32,
            "kind": "adoption",
            "status": "succeeded",
            "result": {"success": True, "inspection_warnings": [warning]},
            "inspection_warnings": [warning],
        }
        compact = bridge.compact_job(manifest)
        self.assertEqual(compact["inspection_warnings"], [warning])
        self.assertEqual(compact["result"]["inspection_warnings"], [warning])

    def test_window_adoption_publishes_a_failed_fallback_and_still_returns(self):
        def synthetic(directory: Path, manifest: dict) -> dict:
            result = {
                "connected": True,
                "delivery_complete": True,
                "disconnect_code": 0,
                "success": True,
                "live": {
                    "origin": str(self.part),
                    "model_type": "part",
                    "healthy": True,
                    "millimeter_units": True,
                    "dependency_free": True,
                    "session_fingerprint": "dev048-fixture-session",
                    "volume_mm3": 10,
                    "inspection": INSPECTION,
                },
                "inspection_warnings": [
                    {
                        "stage": "live",
                        "reason_code": "native_sidecar_write_failed",
                        "fallback_status": "not_attempted",
                        "message": "Cannot write the inspection sidecar file",
                    }
                ],
            }
            bridge.write_json(directory / "native_result.json", result)
            adoption._split_result(result, directory)
            manifest["result"] = result
            return result

        with (
            patch.object(bridge, "build_native", return_value=self.root / "worker.exe"),
            patch.object(adoption, "_native", side_effect=synthetic),
            patch.object(
                inspection_refs,
                "make_ref",
                side_effect=inspection_refs.SidecarWriteFailed("disk is full"),
            ),
        ):
            evidence = adoption.inspect()
        self.assertTrue(evidence["available"])
        self.assertEqual(evidence["inspection_warnings"][0]["fallback_status"], "failed")
        self.assertIn("inspection_warnings", evidence["current_model"])


if __name__ == "__main__":
    unittest.main()
