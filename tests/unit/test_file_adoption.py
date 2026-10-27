"""FEAT-048 offline path/batch regression; synthetic native boundary only."""

import asyncio
import copy
import subprocess
import tempfile
import time
import unittest
from contextlib import ExitStack
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import patch

import bridge
import generic_bridge as general
from creo_mechdog import adoption, inspection_refs, model_registry
from creo_mechdog import file_adoption as batch
from tests.unit.test_adoption import INSPECTION


class PathAdoption(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory(prefix="feat048_")
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name).resolve()
        self.sources = []
        for name in ("one", "two", "three"):
            path = self.root / f"{name}.prt.1"
            path.write_bytes(name.encode())
            self.sources.append(str(path))
        (self.root / "jobs").mkdir()
        (self.root / "models").mkdir()
        stack = ExitStack()
        self.addCleanup(stack.close)
        for obj, name, value in (
            (bridge, "ROOT", self.root),
            (bridge, "JOBS", self.root / "jobs"),
            (general, "MODELS", self.root / "models"),
        ):
            stack.enter_context(patch.object(obj, name, value))
        self.launch = stack.enter_context(patch.object(batch.subprocess, "Popen"))
        stack.enter_context(
            patch.object(bridge, "build_native", return_value=self.root / "worker.exe")
        )
        self.native = stack.enter_context(
            patch.object(adoption, "_native", side_effect=self.synthetic)
        )
        self.behavior = {}
        self.calls = []

    def synthetic(self, directory, manifest):
        request = bridge.read_json(directory / "request.json")
        choice = request["adoption"]
        self.calls.append(copy.deepcopy(choice))
        manifest["worker_started"] = True
        behavior = self.behavior.get((choice["origin"], choice["action"]))
        if behavior == "unknown":
            raise RuntimeError("synthetic incomplete delivery; no Creo")
        if behavior == "timeout":
            raise subprocess.TimeoutExpired("synthetic", adoption.WORKER_SECONDS)
        if behavior == "refused":
            raise adoption.AdoptionRefused("modified_source", "Synthetic source was modified")
        source_state = {
            "origin": choice["origin"],
            "sha256": choice["origin_sha256"],
            "session_model_id": 0,
            "version_stamp": "fixture-stamp",
            "modified": False,
            "provenance": "existing_resident",
            "disk_resident_content_equality": "unknown",
        }
        result = {
            "success": True,
            "delivery_complete": True,
            "disconnect_code": 0,
            "source_unchanged": True,
            "window_unchanged": True,
            "resident_set_changed": False,
            "live": {
                "origin": choice["origin"],
                "model_type": "part",
                "healthy": True,
                "millimeter_units": True,
                "dependency_free": True,
                "source_state": source_state,
                "session_fingerprint": "fixture-session",
                "inspection": INSPECTION,
            },
        }
        if behavior == "inch":
            result["live"].update(
                millimeter_units=False,
                inspection={**INSPECTION, "units": "inch", "volume_mm3": None},
            )
        if behavior in ("unhealthy", "units", "dependencies"):
            result["live"][
                {
                    "unhealthy": "healthy",
                    "units": "millimeter_units",
                    "dependencies": "dependency_free",
                }[behavior]
            ] = False
        if choice["action"] == "apply":
            model = request["model"]
            output = Path(model["output_directory"]) / f"{model['model_name']}.prt.1"
            output.write_bytes(b"synthetic verified managed copy")
            result.update(
                part_file=str(output),
                saved_file_reloaded_and_verified=True,
                inspection=INSPECTION,
                aliases={},
                adopted=True,
            )
            if behavior == "no_reload":
                result["saved_file_reloaded_and_verified"] = False
            if behavior == "source_changed":
                Path(choice["origin"]).write_bytes(b"changed during synthetic copying")
            if behavior == "window_changed":
                result["window_unchanged"] = False
        bridge.write_json(directory / "native_result.json", result, durable=True)
        manifest["result"] = result
        return result

    def inspected(self, paths=None):
        return batch.adopt_file(paths or self.sources)

    def submitted(self, paths=None, key="batch-key-0001", evidence=None):
        paths = paths or self.sources
        evidence = evidence or self.inspected(paths)
        return batch.adopt_file(paths, "apply", evidence["evidence_token"], key)

    def run_parent(self, manifest):
        batch.run(manifest["job_id"], manifest)
        return bridge.get_job(manifest["job_id"], "compact")

    def test_structure_rejected_before_native(self):
        for value in (None, [], ["x"] * 21, [True], [""], 123, ("x",)):
            with self.subTest(value=value), self.assertRaises(ValueError):
                batch.adopt_file(value)
        self.native.assert_not_called()

    def test_scalar_and_list_share_one_ordered_contract(self):
        evidence = self.inspected(self.sources[0])
        manifest = self.submitted([self.sources[0]], evidence=evidence)
        self.assertEqual(manifest["item_count"], 1)
        self.assertEqual(self.launch.call_count, 1)
        terminal = self.run_parent(manifest)
        self.assertTrue(terminal["all_adopted"])
        self.assertEqual(terminal["items"][0]["revision"], 1)

    def test_selector_exact_highest_and_duplicates(self):
        second = Path(self.sources[0]).with_suffix(".2")
        second.write_bytes(b"highest")
        unversioned = str(second.with_suffix(""))
        evidence = self.inspected([unversioned, str(second), self.sources[0]])
        self.assertEqual(
            [i["status"] for i in evidence["items"]], ["eligible", "refused", "eligible"]
        )
        self.assertEqual(evidence["items"][0]["selected_path"], str(second))
        self.assertEqual(evidence["items"][1]["reason"], "duplicate_source")
        self.assertEqual(evidence["items"][1]["duplicate_of"], 0)
        self.assertEqual(len(self.calls), 2)

    def test_duplicate_success_one_registration_and_internal_item_evidence(self):
        result = self.run_parent(self.submitted([self.sources[0], self.sources[0]]))
        self.assertTrue(result["partial_result"])
        self.assertFalse(result["all_adopted"])
        self.assertEqual(result["item_counts"]["succeeded"], 1)
        self.assertEqual(len(list((self.root / "models").glob("*/model.json"))), 1)
        model = general.model_info(result["items"][0]["model_id"])
        self.assertEqual(model["revision"], 1)
        self.assertIsNone(model["pending_job"])
        self.assertEqual(model["parent_job_id"], result["job_id"])

    def test_path_refusal_keeps_verifiable_evidence_and_known_units(self):
        self.behavior[(self.sources[0], "inspect")] = "inch"
        evidence = self.inspected([self.sources[0]])
        item = evidence["items"][0]
        self.assertEqual(item["status"], "refused")
        self.assertEqual(item["reason"], "non_millimeter_units")
        self.assertEqual(item["refusal_details"]["actual_units"], "inch")
        self.assertTrue(item["refusal_details"]["actual_units_known"])
        ref = item["source"]["inspection_ref"]
        inspection_refs.verify_ref(ref)
        self.assertTrue(Path(ref["file"]).resolve().is_relative_to(self.root))
        self.assertEqual(item["source"]["inspection_summary"]["units"], "inch")
        self.assertNotIn("inspection_warnings", item["source"])
        job_directory = bridge.job_path(item["evidence_job_id"])
        probe = bridge.read_json(job_directory / "job.json")
        self.assertEqual(probe["status"], "failed")
        self.assertEqual(probe["reason"], "non_millimeter_units")
        self.assertTrue((job_directory / "request.json").is_file())
        # The refusal keeps its full evidence: the recorded reference resolves.
        inspection_refs.verify_ref(probe["result"]["live"]["inspection_ref"])
        again = bridge.get_job(evidence["job_id"], "full")
        self.assertEqual(again["items"][0]["source"]["inspection_ref"], ref)

    def test_inspect_healthy_refused_healthy_continues_with_live_references(self):
        self.behavior[(self.sources[1], "inspect")] = "units"
        result = self.inspected()
        self.assertEqual(
            [i["status"] for i in result["items"]], ["eligible", "refused", "eligible"]
        )
        self.assertIn("evidence_token", result)
        self.assertEqual(len(self.calls), 3)
        for index in (0, 1, 2):
            source = result["items"][index]["source"]
            ref = source["inspection_ref"]
            inspection_refs.verify_ref(ref)
            self.assertTrue(Path(ref["file"]).resolve().is_relative_to(self.root))
            self.assertEqual(source["inspection_summary"]["units"], "mm")
        self.assertEqual(result["items"][1]["reason"], "non_millimeter_units")
        self.assertEqual(result["items"][1]["refusal_details"]["actual_units"], "mm")

    def test_unreadable_item_reference_refuses_without_reservation_or_revision(self):
        evidence = self.inspected()
        manifest = self.submitted(evidence=evidence)
        Path(evidence["items"][1]["source"]["inspection_ref"]["file"]).unlink()
        result = self.run_parent(manifest)
        self.assertEqual(
            [i["status"] for i in result["items"]], ["succeeded", "refused", "succeeded"]
        )
        refused = result["items"][1]
        self.assertEqual(refused["reason"], "inspection_reference_unavailable")
        # A local reference error never publishes a model reservation and never
        # advances a revision; the following item still commits normally.
        self.assertFalse(general.model_path(refused["model_id"]).exists())
        with self.assertRaises(ValueError):
            general.model_info(refused["model_id"])
        self.assertEqual(general.model_info(result["items"][0]["model_id"])["revision"], 1)
        self.assertEqual(general.model_info(result["items"][2]["model_id"])["revision"], 1)
        self.assertEqual(len([c for c in self.calls if c["action"] == "apply"]), 2)
        self.assertNotIn("inspection_ref", refused["source"])
        self.assertEqual(
            refused["inspection_warnings"][0]["reason_code"],
            "inspection_ref_removed_after_refusal",
        )
        # Replaying the same key re-reads the terminal job without dispatching
        # native work and keeps the same reference meaning.
        replay = self.submitted(evidence=evidence)
        self.assertEqual(replay["job_id"], result["job_id"])
        self.assertNotIn("inspection_ref", replay["items"][1]["source"])
        self.assertEqual(len([c for c in self.calls if c["action"] == "apply"]), 2)

    def test_readonly_path_requests_bind_session_file_stamp_inspection(self):
        evidence = self.inspected([self.sources[0]])
        self.assertEqual(
            evidence["items"][0]["source"]["source_state"]["provenance"], "existing_resident"
        )
        self.assertEqual(
            evidence["items"][0]["source"]["source_state"]["disk_resident_content_equality"],
            "unknown",
        )
        self.run_parent(self.submitted([self.sources[0]], evidence=evidence))
        choice = self.calls[-1]
        self.assertTrue(choice["path_source"])
        self.assertEqual(choice["session_fingerprint"], "fixture-session")
        self.assertEqual(choice["source_state"]["session_model_id"], 0)
        self.assertIn("live_inspection_ref", choice)
        self.assertNotIn("model_name", choice)

    def test_expired_evidence_refused_without_dispatch(self):
        evidence = self.inspected()
        with patch.object(batch.time, "time", return_value=time.time() + 601):
            with self.assertRaisesRegex(ValueError, "expired"):
                self.submitted(evidence=evidence)
        self.launch.assert_not_called()

    def test_pre_submit_byte_change_and_version_selection_change_refused(self):
        evidence = self.inspected()
        Path(self.sources[0]).write_bytes(b"new bytes")
        with self.assertRaisesRegex(ValueError, "identities changed"):
            self.submitted(evidence=evidence)
        unversioned = str(Path(self.sources[1]).with_suffix(""))
        other = self.inspected([unversioned])
        Path(self.sources[1]).with_suffix(".2").write_bytes(b"new version")
        with self.assertRaisesRegex(ValueError, "identities changed"):
            self.submitted([unversioned], evidence=other)

    def test_replay_after_expiry_and_while_channel_busy_never_executes(self):
        evidence = self.inspected()
        manifest = self.submitted(evidence=evidence)
        with bridge.toolkit_lock(operation="synthetic_busy"):
            replay = self.submitted(evidence=evidence)
        self.assertEqual(replay["job_id"], manifest["job_id"])
        terminal = self.run_parent(manifest)
        before = len(self.calls)
        with patch.object(batch.time, "time", return_value=time.time() + 601):
            replay = self.submitted(evidence=evidence)
        self.assertEqual(replay["job_id"], terminal["job_id"])
        self.assertEqual(len(self.calls), before)
        self.assertEqual(self.launch.call_count, 1)

    def test_key_change_order_token_or_identity_refuses(self):
        evidence = self.inspected()
        self.submitted(evidence=evidence)
        with self.assertRaisesRegex(ValueError, "Idempotency"):
            self.submitted(list(reversed(self.sources)), evidence=evidence)
        with self.assertRaisesRegex(ValueError, "Idempotency"):
            self.submitted(evidence={"evidence_token": "a" * 32})
        Path(self.sources[0]).write_bytes(b"changed")
        with self.assertRaisesRegex(ValueError, "Idempotency"):
            self.submitted(evidence=evidence)

    def test_ordinary_refusal_after_success_continues(self):
        manifest = self.submitted()
        self.behavior[(self.sources[1], "apply")] = "refused"
        result = self.run_parent(manifest)
        self.assertEqual(
            [i["status"] for i in result["items"]], ["succeeded", "refused", "succeeded"]
        )
        self.assertEqual(result["status"], "succeeded")
        self.assertTrue(result["partial_result"])
        self.assertIsNone(general.model_info(result["items"][1]["model_id"])["pending_job"])

    def test_unknown_after_success_stops_and_retains_item_protection(self):
        manifest = self.submitted()
        self.behavior[(self.sources[1], "apply")] = "unknown"
        result = self.run_parent(manifest)
        self.assertEqual(result["status"], "unknown_outcome")
        self.assertEqual(
            [i["status"] for i in result["items"]],
            ["succeeded", "unknown_outcome", "not_attempted"],
        )
        self.assertEqual(general.model_info(result["items"][0]["model_id"])["revision"], 1)
        self.assertEqual(
            general.model_info(result["items"][1]["model_id"])["pending_job"],
            result["items"][1]["item_job_id"],
        )
        self.assertFalse(general.model_path(result["items"][2]["model_id"]).exists())
        self.assertEqual(len([c for c in self.calls if c["action"] == "apply"]), 2)

    def test_timeout_stops_and_does_not_reexecute_on_poll_or_runner_restart(self):
        manifest = self.submitted()
        self.behavior[(self.sources[0], "apply")] = "timeout"
        result = self.run_parent(manifest)
        calls = len(self.calls)
        batch.run(manifest["job_id"], manifest)
        bridge.get_job(manifest["job_id"])
        self.assertEqual(len(self.calls), calls)
        self.assertEqual(result["items"][1]["status"], "not_attempted")

    def test_source_change_before_item_copy_is_known_refusal(self):
        manifest = self.submitted()
        Path(self.sources[1]).write_bytes(b"changed before dispatch")
        result = self.run_parent(manifest)
        self.assertEqual(
            [i["status"] for i in result["items"]], ["succeeded", "refused", "succeeded"]
        )
        self.assertEqual(result["items"][1]["reason"], "source_changed")

    def test_source_disappears_before_dispatch_refuses_and_continues(self):
        manifest = self.submitted()
        Path(self.sources[1]).unlink()
        result = self.run_parent(manifest)
        self.assertEqual(
            [i["status"] for i in result["items"]], ["succeeded", "refused", "succeeded"]
        )
        self.assertEqual(result["items"][1]["reason"], "source_unavailable")

    def test_post_copy_verification_failures_remain_unknown(self):
        for behavior in ("source_changed", "no_reload", "window_changed"):
            with self.subTest(behavior=behavior):
                # A fresh fixture per scenario avoids an earlier unknown reservation.
                self.behavior.clear()
                source = self.root / f"{behavior}.prt.1"
                source.write_bytes(b"source")
                paths = [str(source)]
                manifest = self.submitted(paths, key=f"key-{behavior}")
                self.behavior[(str(source), "apply")] = behavior
                result = self.run_parent(manifest)
                self.assertEqual(result["status"], "unknown_outcome")
                self.assertEqual(general.model_info(result["items"][0]["model_id"])["revision"], 0)

    def test_inspect_refusals_and_unknown_stop_are_per_item(self):
        self.behavior[(self.sources[0], "inspect")] = "unhealthy"
        self.behavior[(self.sources[1], "inspect")] = "unknown"
        result = self.inspected()
        self.assertEqual(
            [i["status"] for i in result["items"]], ["refused", "unknown_outcome", "not_attempted"]
        )
        self.assertNotIn("evidence_token", result)
        self.assertEqual(result["items"][0]["reason"], "unhealthy_features")

    def test_unit_dependency_and_assembly_refused_without_registration(self):
        self.behavior[(self.sources[0], "inspect")] = "units"
        self.behavior[(self.sources[1], "inspect")] = "dependencies"
        assembly = self.root / "assembly.asm.1"
        assembly.write_bytes(b"assembly")
        result = self.inspected([*self.sources[:2], str(assembly)])
        self.assertEqual(
            [i["reason"] for i in result["items"]],
            ["non_millimeter_units", "external_dependencies", "unsupported_model_type"],
        )
        self.assertEqual(len(list((self.root / "models").iterdir())), 0)
        self.assertEqual(len(self.calls), 2)

    def test_existing_origin_and_same_token_new_key_cannot_readopt(self):
        evidence = self.inspected([self.sources[0]])
        first = self.run_parent(self.submitted([self.sources[0]], evidence=evidence))
        second = self.run_parent(
            self.submitted([self.sources[0]], evidence=evidence, key="new-key-0002")
        )
        self.assertEqual(second["items"][0]["reason"], "already_adopted")
        self.assertEqual(second["items"][0]["conflict"]["model_id"], first["items"][0]["model_id"])
        self.assertEqual(general.model_info(first["items"][0]["model_id"])["revision"], 1)

    def test_durable_commit_materialization_interrupt_recovers_metadata_once(self):
        manifest = self.submitted()
        original = model_registry.write_model
        failed = False

        def interrupt(path, model):
            nonlocal failed
            if model.get("revision") == 1 and not failed:
                failed = True
                raise OSError("synthetic metadata interruption")
            return original(path, model)

        with patch.object(model_registry, "write_model", side_effect=interrupt):
            batch.run(manifest["job_id"], manifest)
        persisted = bridge.read_json(bridge.job_path(manifest["job_id"]) / "job.json")
        self.assertEqual(persisted["status"], "unknown_outcome")
        before = len(self.calls)
        result = bridge.get_job(manifest["job_id"], "compact")
        self.assertEqual(result["items"][0]["status"], "succeeded")
        self.assertEqual(result["items"][1]["status"], "not_attempted")
        for _ in range(2):
            bridge.get_job(manifest["job_id"])
        self.assertEqual(len(self.calls), before)
        self.assertEqual(general.model_info(result["items"][0]["model_id"])["revision"], 1)

    def test_poll_rereads_parent_under_lock_before_materializing(self):
        accepted = self.submitted()
        stale = copy.deepcopy(accepted)
        stale["status"] = "running"
        terminal = self.run_parent(accepted)
        first = terminal["items"][0]
        stale["items"][0].update(status="reserved", item_job_id=first["item_job_id"])
        path = bridge.job_path(accepted["job_id"]) / "job.json"
        original = bridge.read_json
        reads = 0

        def raced_read(file):
            nonlocal reads
            if Path(file) == path:
                reads += 1
                if reads == 1:
                    return stale
            return original(file)

        with patch.object(bridge, "read_json", side_effect=raced_read):
            self.assertIsNone(batch.resume_committed(accepted["job_id"]))
        self.assertEqual(reads, 2)
        self.assertEqual([i["status"] for i in original(path)["items"]], ["succeeded"] * 3)

    def test_parent_lifetime_covers_twenty_bounded_items(self):
        manifest = self.submitted()
        manifest["created_at"] = (datetime.now(timezone.utc) - timedelta(seconds=1200)).isoformat()
        manifest["item_count"] = 20
        bridge.write_json(bridge.job_path(manifest["job_id"]) / "job.json", manifest)
        with patch.object(bridge, "config", return_value={"native_timeout_seconds": 180}):
            current = bridge.get_job(manifest["job_id"])
        self.assertEqual(current["status"], "queued")
        self.assertGreater(batch.lifetime_seconds(20), 20 * adoption.WORKER_SECONDS)

    def test_one_parent_lock_no_nested_public_apply_and_single_runner(self):
        manifest = self.submitted()
        original = bridge.toolkit_lock
        with (
            patch.object(bridge, "toolkit_lock", wraps=original) as lock,
            patch.object(adoption, "apply", side_effect=AssertionError("nested public apply")),
        ):
            batch.run(manifest["job_id"], manifest)
        self.assertEqual(lock.call_count, 1)
        self.assertEqual(self.launch.call_count, 1)

    def test_failed_journal_commit_stops_before_next_source(self):
        manifest = self.submitted()
        original = bridge.write_json

        def fail_decision(path, data, **kwargs):
            if Path(path).name.startswith("intent-") and data.get("state") == "committed":
                raise OSError("synthetic durable commit failure")
            return original(path, data, **kwargs)

        with patch.object(bridge, "write_json", side_effect=fail_decision):
            batch.run(manifest["job_id"], manifest)
        result = bridge.get_job(manifest["job_id"], "compact")
        self.assertEqual(result["items"][0]["status"], "unknown_outcome")
        self.assertEqual(result["items"][1]["status"], "not_attempted")
        model = general.model_info(result["items"][0]["model_id"])
        self.assertEqual(model["revision"], 0)
        self.assertIsNotNone(model["pending_job"])
        self.assertEqual(len([c for c in self.calls if c["action"] == "apply"]), 1)

    def test_cleanup_metadata_failure_remains_unknown_and_stops(self):
        manifest = self.submitted()
        self.behavior[(self.sources[0], "apply")] = "refused"
        with patch.object(batch, "_release", side_effect=OSError("synthetic closeout failure")):
            result = self.run_parent(manifest)
        self.assertEqual(result["items"][0]["status"], "unknown_outcome")
        self.assertEqual(result["items"][1]["status"], "not_attempted")
        self.assertIsNotNone(general.model_info(result["items"][0]["model_id"])["pending_job"])

    def test_launch_failure_is_replayed_without_launch(self):
        evidence = self.inspected()
        self.launch.side_effect = OSError("synthetic launch failure")
        with self.assertRaises(OSError):
            self.submitted(evidence=evidence)
        self.launch.side_effect = None
        replay = self.submitted(evidence=evidence)
        self.assertEqual(replay["status"], "failed")
        self.assertEqual(replay["items"][0]["status"], "not_attempted")
        self.assertEqual(self.launch.call_count, 1)

    def test_busy_submission_rejects_without_acceptance(self):
        evidence = self.inspected()
        jobs_root = self.root / "jobs"
        before = set(jobs_root.iterdir())
        with bridge.toolkit_lock(operation="other_job"), self.assertRaises(bridge.ToolkitBusy):
            self.submitted(evidence=evidence)
        self.assertEqual(set(jobs_root.iterdir()) - before, set())
        store = jobs_root / "file_adoption"
        intents = list(store.glob("intent-*.json")) if store.exists() else []
        self.assertEqual(intents, [])
        self.assertEqual(len(list((self.root / "models").iterdir())), 0)
        self.launch.assert_not_called()

    def test_busy_inspect_rejects_without_any_job_artifact(self):
        jobs_root = self.root / "jobs"
        before = set(jobs_root.iterdir())
        with bridge.toolkit_lock(operation="other_job"), self.assertRaises(bridge.ToolkitBusy):
            batch.adopt_file(self.sources)
        self.assertEqual(set(jobs_root.iterdir()) - before, set())
        self.assertFalse((jobs_root / "file_adoption").exists())
        self.assertEqual(list((self.root / "models").iterdir()), [])
        self.native.assert_not_called()

    def test_busy_inspect_acquires_lock_before_selection(self):
        # A new submission must not run the expensive per-file selection or
        # identity hashing while the channel is busy.
        with bridge.toolkit_lock(operation="other_job"):
            with patch.object(
                batch, "_select", side_effect=AssertionError("selection ran while busy")
            ):
                with self.assertRaises(bridge.ToolkitBusy):
                    batch.adopt_file(self.sources)
        self.native.assert_not_called()
        self.assertEqual(list((self.root / "jobs").iterdir()), [])

    def test_busy_new_apply_acquires_lock_before_selection(self):
        evidence = self.inspected()
        native_calls = self.native.call_count
        jobs_root = self.root / "jobs"
        before = set(jobs_root.iterdir())
        with bridge.toolkit_lock(operation="other_job"):
            with patch.object(
                batch, "_select", side_effect=AssertionError("selection ran while busy")
            ):
                with self.assertRaises(bridge.ToolkitBusy):
                    self.submitted(evidence=evidence)
        self.assertEqual(set(jobs_root.iterdir()) - before, set())
        store = jobs_root / "file_adoption"
        intents = list(store.glob("intent-*.json")) if store.exists() else []
        self.assertEqual(intents, [])
        self.launch.assert_not_called()
        self.assertEqual(self.native.call_count, native_calls)

    def test_busy_replay_still_binds_identities_readonly(self):
        # Known idempotent replay keeps its path/identity binding contract and
        # returns read-only while the original parent owns the channel.
        evidence = self.inspected()
        manifest = self.submitted(evidence=evidence)
        native_calls = self.native.call_count
        launches = self.launch.call_count
        selected = []
        original = batch._select

        def recording(paths):
            result = original(paths)
            selected.append(paths)
            return result

        with bridge.toolkit_lock(operation="synthetic_busy"):
            with patch.object(batch, "_select", side_effect=recording, autospec=True):
                replay = self.submitted(evidence=evidence)
        self.assertEqual(selected, [self.sources])
        self.assertEqual(replay["job_id"], manifest["job_id"])
        self.assertEqual(self.native.call_count, native_calls)
        self.assertEqual(self.launch.call_count, launches)

    def test_schema_and_distribution_include_real_dependencies(self):
        import server
        from tools.package import source_files

        schemas = asyncio.run(server.mcp.list_tools())
        tool = next(t for t in schemas if t.name == "creo_adopt_file")
        self.assertEqual(
            set(tool.input_schema["properties"]),
            {"file_path", "mode", "evidence_token", "idempotency_key"},
        )
        self.assertIn("src/creo_mechdog/file_adoption.py", server._SOURCE_NAMES)
        self.assertIn("native/adoption_source.h", server._SOURCE_NAMES)
        names = {p.relative_to(server._CODE_ROOT).as_posix() for p in source_files()}
        self.assertTrue(
            {
                "src/creo_mechdog/file_adoption.py",
                "native/adoption_source.h",
                "tests/native/test_adoption_source.cpp",
            }
            <= names
        )


class NativeDeliveryBoundary(unittest.TestCase):
    def test_known_refusal_requires_confirmed_delivery_disconnect_and_no_copy(self):
        for delivered, disconnect, copied, known in (
            (True, 0, False, True),
            (False, 0, False, False),
            (True, 9, False, False),
            (True, 0, True, False),
        ):
            with (
                self.subTest(delivered=delivered, disconnect=disconnect, copied=copied),
                tempfile.TemporaryDirectory() as temporary,
            ):
                directory = Path(temporary)
                result = {
                    "success": False,
                    "delivery_complete": delivered,
                    "disconnect_code": disconnect,
                    "path_source_checked": True,
                    "path_copy_started": copied,
                    "message": "modified_source: synthetic refusal",
                }
                bridge.write_json(directory / "native_result.json", result)
                with (
                    patch.object(bridge, "build_native", return_value=directory / "fake.exe"),
                    patch.object(bridge, "native_environment", return_value={}),
                    patch.object(
                        adoption.subprocess, "run", return_value=subprocess.CompletedProcess([], 1)
                    ),
                ):
                    expected = adoption.AdoptionRefused if known else RuntimeError
                    with self.assertRaises(expected):
                        adoption._native(directory, {"job_id": "a" * 32})


if __name__ == "__main__":
    unittest.main()
