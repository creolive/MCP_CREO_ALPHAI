"""DEV-027 / T11: explicit generation reclamation keeps every unproven reference.

Every fixture is an isolated temporary build tree owned by the test; the real
``build/`` generations are never selected, modified or deleted. The common
channel lock, file occupancy and delete failures are injected through the
module boundary because they cannot be reproduced portably on a temp directory.
"""

import contextlib
import hashlib
import json
import os
import subprocess
import tempfile
import time
import unittest
from pathlib import Path
from unittest.mock import patch

import bridge
from creo_mechdog import generation_reclaim

LOADER = generation_reclaim.LOADER_ROOT
PAYLOAD = generation_reclaim.PAYLOAD_ROOT
A, B, C = "a" * 64, "b" * 64, "c" * 64


def _write(file: Path, value: dict) -> None:
    file.write_text(json.dumps(value) + "\n", encoding="utf-8")


def _stamp(path: Path, seconds: float) -> None:
    os.utime(path, (seconds, seconds))


class _Tree:
    """Temporary build tree whose generation keys are real content digests."""

    def __init__(self, root: Path):
        self.root = root
        self.build = root / "build"
        (self.build / LOADER).mkdir(parents=True)
        (self.build / PAYLOAD).mkdir()

    def payload(self, content: bytes, stamp: float) -> str:
        key = hashlib.sha256(content).hexdigest()
        directory = self.build / PAYLOAD / key
        directory.mkdir()
        (directory / "callback.dll").write_bytes(content)
        _write(directory / "callback_bootstrap.json", {})
        _stamp(directory, stamp)
        return key

    def loader(self, key: str, payload_key: str, stamp: float) -> str:
        directory = self.build / LOADER / key
        directory.mkdir()
        (directory / "loader.dll").write_bytes(f"loader {key}".encode())
        _write(directory / "deployment.json", {"loader_abi": 1, "dll_sha256": payload_key})
        (directory / "protk.dat").write_text("name test\n", encoding="utf-8")
        _stamp(directory, stamp)
        return key

    def records(
        self, current: str = A, setup: str = A, registry: str | None = None, payload_key: str = ""
    ) -> None:
        registry = setup if registry is None else registry
        _write(
            self.build / "blend_loader_build.json",
            {"generation_key": current, "sha256": "0" * 64},
        )
        _write(
            self.build / "blend_callback_setup.json",
            {
                "loader_file": str(self.build / LOADER / setup / "loader.dll"),
                "module_file": str(
                    self.build / PAYLOAD / (payload_key or self.p1) / "callback.dll"
                ),
            },
        )
        (self.build / "blend_callback_protk.dat").write_text(
            f"name test\nstartup dll\nexec_file {self.build / LOADER / registry / 'loader.dll'}"
            "\nend\n",
            encoding="utf-8",
        )


def _healthy(root: Path) -> _Tree:
    """A is current/registered, C is the rollback target, B is reclaimable."""
    tree = _Tree(root)
    tree.p1 = tree.payload(b"payload one", 1000)
    tree.p2 = tree.payload(b"payload two", 1010)
    tree.p3 = tree.payload(b"payload three", 1020)
    tree.p4 = tree.payload(b"payload four", 1030)
    tree.loader(A, tree.p1, 1000)
    tree.loader(B, tree.p2, 1010)
    tree.loader(C, tree.p2, 1020)
    tree.records()
    return tree


class ReclaimCase(unittest.TestCase):
    def setUp(self):
        self._directory = tempfile.TemporaryDirectory()
        self.root = Path(self._directory.name)
        self.addCleanup(self._directory.cleanup)
        patcher = patch.object(bridge, "ROOT", self.root)
        patcher.start()
        self.addCleanup(patcher.stop)
        lock = patch.object(bridge, "toolkit_lock", return_value=contextlib.nullcontext())
        lock.start()
        self.addCleanup(lock.stop)

    def inspect(self, tree: _Tree, *targets: tuple[str, str]) -> dict:
        keys = [{"root": root, "key": key} for root, key in targets]
        return generation_reclaim.reclaim_generations("inspect", keys)


class InspectTests(ReclaimCase):
    def test_reference_classes_keep_current_registered_runtime_and_retained(self):
        tree = _healthy(self.root)
        result = self.inspect(
            tree,
            (LOADER, A),
            (LOADER, B),
            (LOADER, C),
            (PAYLOAD, tree.p1),
            (PAYLOAD, tree.p2),
            (PAYLOAD, tree.p3),
            (PAYLOAD, tree.p4),
        )
        status = {(item["root"], item["generation_key"]): item for item in result["items"]}
        self.assertEqual(status[(LOADER, A)]["reasons"], ["current", "registered"])
        self.assertEqual(status[(LOADER, C)]["reasons"], ["rollback_retention"])
        self.assertEqual(status[(LOADER, B)]["status"], "reclaimable")
        self.assertIn("current", status[(PAYLOAD, tree.p1)]["reasons"])
        self.assertIn("referenced_by_loader_generation", status[(PAYLOAD, tree.p2)]["reasons"])
        self.assertEqual(status[(PAYLOAD, tree.p4)]["reasons"], ["rollback_retention"])
        self.assertEqual(status[(PAYLOAD, tree.p3)]["status"], "reclaimable")
        self.assertEqual(result["rollback_retained"], {LOADER: C, PAYLOAD: tree.p4})
        self.assertEqual(
            sorted(item["generation_key"] for item in result["reclaimable"]),
            sorted([B, tree.p3]),
        )
        # Inspect deletes nothing and connects to nothing.
        self.assertTrue((tree.build / LOADER / B).is_dir())
        self.assertEqual(result["deletes"], 0)
        self.assertEqual(result["toolkit_connections"], 0)
        self.assertFalse(result["dll_loaded"])
        self.assertTrue(result["read_only"])

    def test_occupied_generation_is_kept(self):
        tree = _healthy(self.root)
        with patch.object(generation_reclaim, "_locked_files", return_value=["loader.dll"]):
            result = self.inspect(tree, (LOADER, B))
        self.assertEqual(result["items"][0]["status"], "kept")
        self.assertIn("file_locked", result["items"][0]["reasons"])
        self.assertIsNone(result["evidence_token"])

    def test_missing_records_keep_every_generation(self):
        tree = _healthy(self.root)
        (tree.build / "blend_loader_build.json").unlink()
        result = self.inspect(tree, (LOADER, B), (PAYLOAD, tree.p3))
        self.assertEqual(result["reclaimable"], [])
        self.assertIn("build_stamp_missing", result["items"][0]["reasons"])
        self.assertIn("records_not_definitive", result["items"][1]["reasons"])
        self.assertFalse(result["inventory"]["records_definitive"])
        self.assertIsNone(result["evidence_token"])

    def test_conflicting_records_keep_generations(self):
        tree = _healthy(self.root)
        tree.records(current=A, setup=A, registry=B)
        result = self.inspect(tree, (LOADER, B), (PAYLOAD, tree.p3))
        self.assertTrue(result["inventory"]["record_conflict"])
        self.assertEqual(result["reclaimable"], [])
        self.assertIn("record_conflict", result["items"][0]["reasons"])

    def test_unexpected_content_and_not_a_generation_are_kept(self):
        tree = _healthy(self.root)
        (tree.build / LOADER / B / "operator-note.txt").write_text("keep me", encoding="utf-8")
        (tree.build / LOADER / ("d" * 64)).mkdir()
        (tree.build / LOADER / ("d" * 64) / "readme.txt").write_text("x", encoding="utf-8")
        result = self.inspect(tree, (LOADER, B), (LOADER, "d" * 64))
        self.assertEqual(result["reclaimable"], [])
        self.assertIn("unexpected_content", result["items"][0]["reasons"])
        self.assertIn("not_a_generation", result["items"][1]["reasons"])

    def test_directory_link_is_refused(self):
        tree = _healthy(self.root)
        outside = self.root / "outside"
        outside.mkdir()
        (outside / "loader.dll").write_bytes(b"outside")
        link = tree.build / LOADER / ("e" * 64)
        if not _make_link(outside, link, directory=True):
            self.skipTest("This host cannot create a directory link")
        result = self.inspect(tree, (LOADER, "e" * 64))
        self.assertEqual(result["items"][0]["status"], "kept")
        self.assertIn("reparse_point", result["items"][0]["reasons"])
        self.assertIsNone(result["evidence_token"])

    def test_file_link_inside_generation_is_refused(self):
        tree = _healthy(self.root)
        target = self.root / "outside.dll"
        target.write_bytes(b"outside")
        link = tree.build / LOADER / B / "callback_result.json"
        if not _make_link(target, link, directory=False):
            self.skipTest("This host cannot create a file symlink")
        result = self.inspect(tree, (LOADER, B))
        self.assertEqual(result["items"][0]["status"], "kept")
        self.assertIn("reparse_point", result["items"][0]["reasons"])

    def test_selection_rejects_traversal_absolute_paths_and_bad_modes(self):
        valid = [{"root": LOADER, "key": B}]
        for keys in (
            [{"root": LOADER, "key": "../" + B}],
            [{"root": LOADER, "key": "E:\\outside"}],
            [{"root": LOADER, "key": B + "\\.."}],
            [{"root": "models", "key": B}],
            [{"root": LOADER, "key": B.upper()}],
            [{"root": PAYLOAD, "key": B + "-" + "0" * 12}],
            [{"root": LOADER, "key": B}, {"root": LOADER, "key": B}],
            [{"root": LOADER, "key": B, "extra": 1}],
            [],
        ):
            with self.subTest(keys=keys):
                with self.assertRaises(ValueError):
                    generation_reclaim.reclaim_generations("inspect", keys)
        with self.assertRaises(ValueError):
            generation_reclaim.reclaim_generations("delete", valid)
        with self.assertRaises(ValueError):
            generation_reclaim.reclaim_generations("inspect", valid, "t" * 32)
        with self.assertRaises(ValueError):
            generation_reclaim.reclaim_generations("apply", evidence_token="t" * 32)
        with self.assertRaises(ValueError):
            generation_reclaim.reclaim_generations(
                "apply", evidence_token="t" * 32, idempotency_key="short"
            )


class ApplyTests(ReclaimCase):
    def apply(self, tree: _Tree, key: str = "reclaim-key-1", token: str | None = None) -> dict:
        evidence = token or self.inspect(tree, (LOADER, B), (PAYLOAD, tree.p3))["evidence_token"]
        return generation_reclaim.reclaim_generations("apply", None, evidence, key)

    def test_successful_reclaim_removes_only_authorized_generations(self):
        tree = _healthy(self.root)
        result = self.apply(tree)
        self.assertEqual(result["state"], "completed")
        self.assertFalse(result["replayed"])
        self.assertEqual([item["generation_key"] for item in result["reclaimed"]], [B, tree.p3])
        self.assertFalse((tree.build / LOADER / B).exists())
        self.assertFalse((tree.build / PAYLOAD / tree.p3).exists())
        self.assertTrue((tree.build / LOADER / A).is_dir())
        self.assertTrue((tree.build / LOADER / C).is_dir())
        self.assertTrue((tree.build / PAYLOAD / tree.p4).is_dir())
        self.assertGreater(result["bytes_reclaimed"], 0)
        self.assertTrue(result["complete"])
        intent = json.loads(
            (
                self.root
                / "generation_reclaim"
                / f"intent-{generation_reclaim._key_digest('reclaim-key-1')}.json"
            ).read_text(encoding="utf-8")
        )
        self.assertEqual(intent["state"], "completed")
        self.assertEqual(
            intent["idempotency_key_sha256"], generation_reclaim._key_digest("reclaim-key-1")
        )
        self.assertEqual([item["status"] for item in intent["items"]], ["reclaimed"] * 2)
        self.assertEqual(intent["items"][0]["deleted_files"], 3)
        self.assertEqual(intent["toolkit_connections"], 0)
        self.assertFalse(intent["dll_loaded"])

    def test_same_key_replay_does_not_delete_again(self):
        tree = _healthy(self.root)
        token = self.inspect(tree, (LOADER, B), (PAYLOAD, tree.p3))["evidence_token"]
        first = self.apply(tree, token=token)
        self.assertEqual(first["counts"]["reclaimed"], 2)
        (tree.build / LOADER / B).mkdir()
        (tree.build / LOADER / B / "loader.dll").write_bytes(b"recreated")
        replay = self.apply(tree, token=token)
        self.assertTrue(replay["replayed"])
        self.assertEqual(replay["state"], "completed")
        self.assertEqual(replay["reclaimed"], first["reclaimed"])
        self.assertTrue((tree.build / LOADER / B / "loader.dll").is_file())

    def test_same_key_with_another_token_is_refused(self):
        tree = _healthy(self.root)
        first = self.inspect(tree, (LOADER, B))
        second = self.inspect(tree, (LOADER, B))
        generation_reclaim.reclaim_generations(
            "apply", None, first["evidence_token"], "reclaim-key-2"
        )
        with self.assertRaises(ValueError):
            generation_reclaim.reclaim_generations(
                "apply", None, second["evidence_token"], "reclaim-key-2"
            )
        self.assertTrue((tree.build / LOADER / C).is_dir())

    def test_expired_evidence_is_refused(self):
        tree = _healthy(self.root)
        token = self.inspect(tree, (LOADER, B))["evidence_token"]
        record = self.root / "generation_reclaim" / f"evidence-{token}.json"
        stored = json.loads(record.read_text(encoding="utf-8"))
        stored["created"] = time.time() - generation_reclaim.TOKEN_SECONDS - 1
        _write(record, stored)
        with self.assertRaisesRegex(ValueError, "expired"):
            generation_reclaim.reclaim_generations("apply", None, token, "reclaim-key-3")
        self.assertTrue((tree.build / LOADER / B).is_dir())

    def test_changed_content_after_inspect_is_refused(self):
        tree = _healthy(self.root)
        token = self.inspect(tree, (LOADER, B))["evidence_token"]
        (tree.build / LOADER / B / "loader.dll").write_bytes(b"rebuilt loader")
        with self.assertRaisesRegex(ValueError, "content_changed"):
            generation_reclaim.reclaim_generations("apply", None, token, "reclaim-key-4")
        self.assertTrue((tree.build / LOADER / B).is_dir())

    def test_new_reference_after_inspect_is_refused(self):
        tree = _healthy(self.root)
        token = self.inspect(tree, (LOADER, B))["evidence_token"]
        tree.records(current=A, setup=A, registry=B)
        with self.assertRaisesRegex(ValueError, "reference_changed"):
            generation_reclaim.reclaim_generations("apply", None, token, "reclaim-key-5")
        self.assertTrue((tree.build / LOADER / B).is_dir())

    def test_concurrent_build_lock_refuses_both_modes(self):
        tree = _healthy(self.root)

        def busy(*args, **kwargs):
            raise bridge.ToolkitBusy(holder={"operation": "build_native"})

        with patch.object(bridge, "toolkit_lock", side_effect=busy):
            with self.assertRaises(bridge.ToolkitBusy):
                generation_reclaim.reclaim_generations("inspect", [{"root": LOADER, "key": B}])
            with self.assertRaises(bridge.ToolkitBusy):
                generation_reclaim.reclaim_generations("apply", None, "f" * 32, "reclaim-key-6")
        self.assertTrue((tree.build / LOADER / B).is_dir())

    def test_retention_change_at_apply_keeps_the_item(self):
        tree = _healthy(self.root)
        token = self.inspect(tree, (LOADER, B))["evidence_token"]
        # C disappears between inspect and apply: B is now the rollback target.
        for name in ("loader.dll", "deployment.json", "protk.dat"):
            (tree.build / LOADER / C / name).unlink()
        (tree.build / LOADER / C).rmdir()
        result = generation_reclaim.reclaim_generations("apply", None, token, "reclaim-key-7")
        self.assertEqual(result["counts"]["reclaimed"], 0)
        self.assertEqual(result["counts"]["kept"], 1)
        self.assertIn("rollback_retention", result["kept"][0]["reasons"])
        self.assertTrue((tree.build / LOADER / B / "loader.dll").is_file())

    def test_partial_failure_reports_real_results(self):
        tree = _healthy(self.root)
        token = self.inspect(tree, (LOADER, B), (PAYLOAD, tree.p3))

        original = Path.unlink

        def failing(path, missing_ok=False):
            if path.parent.name == tree.p3 and path.name == "callback.dll":
                raise PermissionError(13, "file is in use")
            return original(path, missing_ok=missing_ok)

        with patch.object(Path, "unlink", failing):
            result = generation_reclaim.reclaim_generations(
                "apply", None, token["evidence_token"], "reclaim-key-8"
            )
        self.assertFalse(result["complete"])
        self.assertEqual([item["generation_key"] for item in result["reclaimed"]], [B])
        self.assertEqual([item["generation_key"] for item in result["failed"]], [tree.p3])
        failed = result["failed"][0]
        self.assertIn("delete_failed", failed["reasons"])
        self.assertFalse((tree.build / LOADER / B).exists())
        self.assertTrue((tree.build / PAYLOAD / tree.p3 / "callback.dll").is_file())
        self.assertIn("not rolled back", result["note"])

    def test_interrupted_intent_replays_without_deleting(self):
        tree = _healthy(self.root)
        token = self.inspect(tree, (LOADER, B))["evidence_token"]
        pointer = (
            self.root
            / "generation_reclaim"
            / f"intent-{generation_reclaim._key_digest('reclaim-key-9')}.json"
        )
        _write(
            pointer,
            {
                "mode": "apply",
                "state": "in_progress",
                "evidence_token": token,
                "items": [
                    {"root": LOADER, "generation_key": B, "status": "pending", "reasons": []}
                ],
            },
        )
        result = generation_reclaim.reclaim_generations("apply", None, token, "reclaim-key-9")
        self.assertTrue(result["replayed"])
        self.assertEqual(result["counts"]["unknown"], 1)
        self.assertEqual(result["unknown"][0]["reasons"], ["interrupted"])
        self.assertTrue((tree.build / LOADER / B).is_dir())

    def test_unauthorized_target_is_kept_at_apply(self):
        tree = _healthy(self.root)

        def locked(directory, names):
            return ["loader.dll"] if Path(directory).name == B else []

        # B is occupied at inspect time, so the token never authorizes it even
        # after the lock clears; only the authorized payload may be deleted.
        with patch.object(generation_reclaim, "_locked_files", side_effect=locked):
            result = self.inspect(tree, (LOADER, B), (PAYLOAD, tree.p3))
        self.assertEqual(result["items"][0]["reasons"], ["file_locked"])
        applied = generation_reclaim.reclaim_generations(
            "apply", None, result["evidence_token"], "reclaim-key-a"
        )
        self.assertEqual([item["generation_key"] for item in applied["reclaimed"]], [tree.p3])
        kept = {item["generation_key"]: item["reasons"] for item in applied["kept"]}
        self.assertEqual(kept[B], ["not_authorized_by_evidence"])
        self.assertTrue((tree.build / LOADER / B).is_dir())


class ReadOnlyBoundaryTests(ReclaimCase):
    def test_no_generation_is_touched_anywhere_else(self):
        tree = _healthy(self.root)
        before = _snapshot(tree.build)
        self.inspect(
            tree, (LOADER, A), (LOADER, B), (LOADER, C), (PAYLOAD, tree.p1), (PAYLOAD, tree.p3)
        )
        self.assertEqual(_snapshot(tree.build), before)

    def test_inventory_and_reclaim_share_the_reference_classification(self):
        tree = _healthy(self.root)
        result = self.inspect(tree, (LOADER, B), (PAYLOAD, tree.p3))
        # The inventory reports both unreferenced generations; this tool keeps
        # the rollback targets C and p4 and only authorizes B and p3.
        self.assertEqual(sorted(result["inventory"]["reclaim_candidates"]), [B, C])
        self.assertEqual(
            sorted(result["inventory"]["reclaim_candidates_payload"]),
            sorted([tree.p3, tree.p4]),
        )
        self.assertTrue(result["inventory"]["records_definitive"])


def _snapshot(root: Path) -> dict:
    return {
        str(path.relative_to(root)): path.read_bytes()
        for path in sorted(root.rglob("*"))
        if path.is_file()
    }


def _make_link(target: Path, link: Path, *, directory: bool) -> bool:
    try:
        os.symlink(target, link, target_is_directory=directory)
        return True
    except (OSError, NotImplementedError):
        pass
    if not directory:
        return False
    created = subprocess.run(
        ["cmd", "/c", "mklink", "/J", str(link), str(target)],
        capture_output=True,
        check=False,
    )
    return created.returncode == 0 and link.exists()


if __name__ == "__main__":
    unittest.main()
