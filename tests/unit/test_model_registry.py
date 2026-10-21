"""BUG-077: registry split, migration and structured budget errors.

In-process checks for the unified registry persistence: model.json keeps small
control records while aliases/inspection details live in content-addressed
sidecars; a legacy oversized entry is refused with a structured error that
names the migration tools instead of silently loading; reconcile admission
compares records semantically so a lazy split never reads as a model change;
and the migration tool splits entries and their job evidence idempotently with
backups and an append-only log. FEAT-047 health reporting is covered here too.
"""

import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import bridge
import generic_bridge as general
from creo_mechdog import model_registry, registry_ops

ALIASES = {
    "sk_big": {
        "entity_ids": {
            f"line_{i:05d}": {"id": 1000 + i, "geometry": [0.1 * i] * 8} for i in range(400)
        },
        "dimension_ids": {},
    }
}
INSPECTION = {
    "healthy": True,
    "features": [{"id": 1, "type": 100, "geometry_items": [], "dimensions": []}],
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


def _model(model_id: str, **overrides) -> dict:
    return {
        "model_id": model_id,
        "model_name": f"part_{model_id[:8]}",
        "revision": 3,
        "status": "ready",
        "model_type": "part",
        "created_at": "2026-10-21T00:00:00Z",
        "updated_at": "2026-10-21T00:00:00Z",
        "output_directory": str(Path(bridge.ROOT) / "models" / model_id / "output"),
        "part_file": None,
        "aliases": ALIASES,
        "inspection": INSPECTION,
        **overrides,
    }


class RegistryBase(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory(prefix="bug077_registry_")
        self.root = Path(self.temporary.name)
        (self.root / "jobs").mkdir()
        (self.root / "models").mkdir()
        for patcher in (
            patch.object(bridge, "ROOT", self.root),
            patch.object(bridge, "JOBS", self.root / "jobs"),
            patch.object(general, "MODELS", self.root / "models"),
        ):
            patcher.start()
            self.addCleanup(patcher.stop)

    def tearDown(self):
        self.temporary.cleanup()

    def entry(self, model_id: str, model: dict | None = None) -> Path:
        directory = general.MODELS / model_id
        directory.mkdir(parents=True, exist_ok=True)
        model_registry.write_model(directory, model or _model(model_id))
        return directory

    def legacy_entry(self, model_id: str, **overrides) -> Path:
        """Write an old-format entry: full payloads inlined in model.json."""
        directory = general.MODELS / model_id
        directory.mkdir(parents=True, exist_ok=True)
        (directory / "model.json").write_text(
            json.dumps(_model(model_id, **overrides)), encoding="utf-8"
        )
        return directory


class WriteAndResolve(RegistryBase):
    def test_write_splits_details_into_sidecars_and_control_record_stays_small(self):
        directory = self.entry("a" * 32)
        raw = (directory / "model.json").read_text(encoding="utf-8")
        self.assertNotIn("sk_big", raw)  # inline payload must not reach the control record
        self.assertLess(len(raw), 64 * 1024)
        model = model_registry.read_control(directory)
        self.assertIsNone(model.get("aliases"))
        self.assertIsNone(model.get("inspection"))
        resolved = model_registry.aliases_of(model)
        self.assertEqual(resolved["sk_big"]["dimension_ids"], {})
        inspection = model_registry.inspection_of(model)
        self.assertEqual(inspection["volume_mm3"], INSPECTION["volume_mm3"])
        self.assertEqual(model.get("inspection_summary", {}).get("counts", {}).get("features"), 1)

    def test_sidecars_are_content_addressed_and_rerun_is_idempotent(self):
        directory = self.entry("b" * 32)
        first = model_registry.read_control(directory)
        before = sorted(p.name for p in (directory / "details").glob("*.json"))
        model_registry.write_model(directory, dict(first, updated_at="later"))
        after = sorted(p.name for p in (directory / "details").glob("*.json"))
        self.assertEqual(before, after)

    def test_semantic_view_is_form_independent(self):
        directory = self.entry("c" * 32)
        split = model_registry.read_control(directory)
        legacy = _model("c" * 32)
        self.assertEqual(model_registry.semantic_view(split), model_registry.semantic_view(legacy))

    def test_tampered_detail_reference_is_refused(self):
        directory = self.entry("d" * 32)
        model = model_registry.read_control(directory)
        ref = model["aliases_ref"]
        (Path(ref["file"])).write_text("{}", encoding="utf-8")
        from creo_mechdog.inspection_refs import InspectionRefInvalid

        with self.assertRaises(InspectionRefInvalid):
            model_registry.aliases_of(model)


class BudgetErrors(RegistryBase):
    def test_oversized_entry_is_refused_with_structured_payload(self):
        model_id = "e" * 32
        directory = general.MODELS / model_id
        directory.mkdir(parents=True)
        bloat = dict(
            _model(model_id), aliases={**ALIASES, "extra": {"blob": "x" * 17 * 1024 * 1024}}
        )
        (directory / "model.json").write_text(json.dumps(bloat), encoding="utf-8")
        with self.assertRaises(model_registry.RegistryBudgetExceeded) as caught:
            general.model_info(model_id)
        payload = caught.exception.payload
        self.assertEqual(payload["reason_code"], "REGISTRY_METADATA_BUDGET_EXCEEDED")
        self.assertEqual(payload["metadata_kind"], "model_registry")
        self.assertEqual(payload["actual_bytes"], (directory / "model.json").stat().st_size)
        self.assertEqual(payload["budget_bytes"], model_registry.BUDGET_BYTES)
        self.assertIn("creo_registry_health", payload["recovery"])
        self.assertIn("creo_migrate_registry", payload["recovery"])
        # The file is never modified by the refusal.
        self.assertEqual(
            (directory / "model.json").stat().st_size,
            (directory / "model.json").stat().st_size,
        )
        # The structured payload flows through the public error text contract.
        import creo_mechdog.adoption as adoption

        with self.assertRaises(adoption.AdoptionMetadataBudgetExceeded) as adopt_caught:
            adoption._origin_conflict(self.root / "user_parts" / "whatever.prt")
        self.assertEqual(
            adopt_caught.exception.payload["reason_code"],
            "ADOPTION_METADATA_BUDGET_EXCEEDED",
        )
        self.assertEqual(adopt_caught.exception.payload["metadata_kind"], "model_registry")

    def test_conflict_scan_refuses_unreadable_entry_instead_of_skipping(self):
        directory = general.MODELS / ("f" * 32)
        directory.mkdir(parents=True)
        (directory / "model.json").write_text("{not json", encoding="utf-8")
        import creo_mechdog.adoption as adoption

        with self.assertRaises(adoption.AdoptionRefused) as caught:
            adoption._origin_conflict(self.root / "user_parts" / "whatever.prt")
        self.assertEqual(caught.exception.reason, "registry_entry_unreadable")

    def test_conflict_scan_still_detects_conflicts_after_split(self):
        model_id = "a" * 32
        directory = self.entry(
            model_id,
            _model(
                model_id,
                output_directory=str(self.root / "models" / model_id / "output"),
                part_file=None,
            ),
        )
        model = model_registry.read_control(directory)
        model["adopted_from"] = {
            "origin": str(self.root / "user_parts" / "001.prt"),
            "origin_sha256": "0" * 64,
            "state": "pending",
        }
        model_registry.write_model(directory, model)
        import creo_mechdog.adoption as adoption

        conflict = adoption._origin_conflict(self.root / "user_parts" / "001.prt")
        self.assertIsNotNone(conflict)
        self.assertEqual(conflict["model_id"], model_id)


class Migration(RegistryBase):
    def test_inspect_lists_legacy_entries_without_touching_files(self):
        self.legacy_entry("1" * 32)
        self.legacy_entry("2" * 32)
        raw = (general.MODELS / ("2" * 32) / "model.json").read_bytes()
        report = registry_ops.migrate("inspect")
        self.assertEqual(report["entries_needing_migration"], 2)
        self.assertEqual((general.MODELS / ("2" * 32) / "model.json").read_bytes(), raw)

    def test_apply_splits_entry_and_job_evidence_with_backup_and_log(self):
        model_id = "3" * 32
        directory = self.legacy_entry(model_id, last_job="a" * 32)
        job_dir = bridge.job_path("a" * 32)
        job_dir.mkdir(parents=True)
        bridge.write_json(
            job_dir / "job.json",
            {
                "job_id": "a" * 32,
                "status": "succeeded",
                "result": {"success": True, "aliases": ALIASES, "inspection": INSPECTION},
            },
        )
        bridge.write_json(
            job_dir / "request.json",
            {"model": dict(_model(model_id), aliases=ALIASES, inspection=INSPECTION)},
        )
        original_entry = (directory / "model.json").read_bytes()
        original_job = (job_dir / "job.json").read_bytes()
        report = registry_ops.migrate("apply", idempotency_key="migrate-batch-01")
        self.assertEqual(report["migrated"], 1)
        self.assertEqual(report["refused"], 0)
        backup = directory / "model.json.pre-split-bak"
        self.assertTrue(backup.is_file())
        self.assertEqual(json.loads(backup.read_text(encoding="utf-8"))["aliases"], ALIASES)
        # Job evidence no longer inlines payloads; sidecars live in the job dir.
        job = bridge.read_json(job_dir / "job.json")
        self.assertNotIn("aliases", job["result"])
        self.assertIn("aliases_ref", job["result"])
        request = bridge.read_json(job_dir / "request.json")
        self.assertNotIn("aliases", request["model"])
        self.assertIn("aliases_ref", request["model"])
        self.assertTrue((job_dir / "details").glob("detail-aliases-*.json"))
        log = (general.MODELS / "registry-migration.jsonl").read_text(encoding="utf-8")
        self.assertIn(model_id, log)
        # Migrated entry reads cleanly and resolves the same content.
        control = model_registry.read_control(directory)
        self.assertEqual(model_registry.aliases_of(control), ALIASES)
        self.assertNotIn("sk_big", (directory / "model.json").read_text(encoding="utf-8"))
        self.assertNotEqual(original_entry, (directory / "model.json").read_bytes())
        self.assertNotEqual(original_job, (job_dir / "job.json").read_bytes())

    def test_apply_is_idempotent_and_key_conflicts_are_refused(self):
        self.legacy_entry("4" * 32)
        first = registry_ops.migrate("apply", idempotency_key="migrate-batch-02")
        self.assertEqual(first["migrated"], 1)
        replay = registry_ops.migrate("apply", idempotency_key="migrate-batch-02")
        self.assertTrue(replay["replayed"])
        self.assertEqual(replay["migrated"], first["migrated"])
        with self.assertRaises(ValueError):
            registry_ops.migrate("apply", targets=["4" * 32], idempotency_key="migrate-batch-02")
        with self.assertRaises(ValueError):
            registry_ops.migrate("apply", idempotency_key="short")

    def test_apply_refuses_corrupt_entry_and_migrates_the_rest(self):
        good = self.legacy_entry("5" * 32)
        bad = general.MODELS / ("6" * 32)
        bad.mkdir(parents=True)
        (bad / "model.json").write_text("{broken", encoding="utf-8")
        report = registry_ops.migrate("apply", idempotency_key="migrate-batch-03")
        self.assertEqual(report["migrated"], 1)
        self.assertEqual(report["refused"], 1)
        self.assertIn("{broken", (bad / "model.json").read_text(encoding="utf-8"))
        self.assertTrue(model_registry.read_control(good).get("aliases_ref"))


class Health(RegistryBase):
    def test_report_classifies_ok_warning_over_budget_corrupt_and_legacy(self):
        self.entry("a" * 32)
        big = general.MODELS / ("b" * 32)
        big.mkdir(parents=True)
        bloat = dict(_model("b" * 32), aliases={"blob": "x" * 17 * 1024 * 1024})
        (big / "model.json").write_text(json.dumps(bloat), encoding="utf-8")
        near = general.MODELS / ("c" * 32)
        near.mkdir(parents=True)
        # A migrated (already split) entry that merely sits near the budget.
        filler = "x" * (int(model_registry.BUDGET_BYTES * 0.85) - 1200)
        model_registry.write_model(
            near, dict(_model("c" * 32, aliases={}, inspection={}), note=filler)
        )
        broken = general.MODELS / ("d" * 32)
        broken.mkdir(parents=True)
        (broken / "model.json").write_text("{nope", encoding="utf-8")
        report = registry_ops.health()
        self.assertEqual(report["entry_count"], 4)
        self.assertEqual(report["summary"]["ok"], 1)
        self.assertEqual(report["summary"]["warning"], 1)
        self.assertEqual(report["summary"]["over_budget"], 1)
        self.assertEqual(report["summary"]["corrupt"], 1)
        self.assertEqual(report["over_budget"]["count"], 1)
        self.assertTrue(report["over_budget"]["complete"])
        self.assertEqual(report["over_budget"]["entries"][0]["model_id"], "b" * 32)
        self.assertEqual(report["over_budget"]["entries"][0]["state"], "over_budget")
        self.assertGreater(
            report["over_budget"]["entries"][0]["model_json_bytes"], model_registry.BUDGET_BYTES
        )
        self.assertTrue(report["migration"]["needed"] >= 1)
        # A corrupt entry never ends the report; ok entry is still present.
        self.assertEqual(report["entries"][0]["model_id"], "a" * 32)
        self.assertIsNone(report["next_cursor"])
        self.assertEqual(report["corrupt"]["count"], 1)

    def test_migrated_entry_reports_reference_forms(self):
        directory = self.legacy_entry("e" * 32)
        report = registry_ops.migrate(
            "apply", targets=[directory.name], idempotency_key="health-check-01"
        )
        self.assertEqual(report["migrated"], 1)
        health = registry_ops.health()
        entry = next(e for e in health["entries"] if e["model_id"] == directory.name)
        self.assertEqual(entry["state"], "ok")
        self.assertEqual(entry["details"]["aliases"]["form"], "reference")
        self.assertEqual(entry["details"]["inspection"]["form"], "reference")
        self.assertEqual(entry["details"]["last_live_inspection"]["form"], "absent")


class Pagination(RegistryBase):
    def test_entry_listing_is_bounded_and_pages_through_every_entry(self):
        for index in range(7):
            model_registry.write_model(general.MODELS / f"{index:032d}", _model(f"{index:032d}"))
        first = registry_ops.health(limit=3)
        self.assertEqual(len(first["entries"]), 3)
        self.assertTrue(first["has_more"])
        self.assertEqual(first["entry_count"], 7)
        seen = [e["model_id"] for e in first["entries"]]
        cursor = first["next_cursor"]
        while cursor:
            page = registry_ops.health(limit=3, cursor=cursor)
            seen.extend(e["model_id"] for e in page["entries"])
            cursor = page["next_cursor"]
        self.assertEqual(seen, [f"{i:032d}" for i in range(7)])
        self.assertEqual(len(set(seen)), 7)
        with self.assertRaises(ValueError):
            registry_ops.health(limit=0)


if __name__ == "__main__":
    unittest.main()
