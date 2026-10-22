"""DEV-027 generation inventory: reference classification keeps unprovable generations."""

import hashlib
import json
import os
import time
import unittest
from pathlib import Path

from creo_mechdog.blend_callback import generation_inventory


def _digest_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


class _Build:
    """Temporary build tree with loader/payload generations and local records."""

    def __init__(self, root: Path):
        self.root = root
        self.build = root / "build"
        (self.build / "blend_loader").mkdir(parents=True)
        (self.build / "blend_callback").mkdir()
        self.payload_keys: list[str] = []

    def payload(self, content: bytes) -> str:
        key = _digest_bytes(content)
        directory = self.build / "blend_callback" / key
        directory.mkdir(exist_ok=True)
        (directory / "callback.dll").write_bytes(content)
        (directory / "callback_bootstrap.json").write_text("{}\n", encoding="utf-8")
        self.payload_keys.append(key)
        return key

    def generation(
        self,
        key: str,
        payload_key: str | None,
        *,
        deployment: bool = True,
        ready_age_seconds: float | None = None,
    ) -> str:
        directory = self.build / "blend_loader" / key
        directory.mkdir(exist_ok=True)
        (directory / "loader.dll").write_bytes(f"loader {key}".encode())
        if deployment:
            (directory / "deployment.json").write_text(
                json.dumps({"loader_abi": 1, "dll_sha256": payload_key}) + "\n",
                encoding="utf-8",
            )
        if ready_age_seconds is not None:
            ready = directory / "callback_result.json"
            ready.write_text("{}\n", encoding="utf-8")
            stamp = time.time() - ready_age_seconds
            os.utime(ready, (stamp, stamp))
        return key

    def records(
        self,
        current: str | None,
        setup_loader: Path | None,
        registry_loader: Path | None,
        payload_current: str | None,
    ) -> None:
        if current is not None:
            (self.build / "blend_loader_build.json").write_text(
                json.dumps({"generation_key": current, "sha256": "0" * 64}) + "\n",
                encoding="utf-8",
            )
        loader_dir = self.build / "blend_loader"
        payload_dir = self.build / "blend_callback"
        if setup_loader is not None and payload_current is not None:
            (self.build / "blend_callback_setup.json").write_text(
                json.dumps(
                    {
                        "loader_file": str((loader_dir / setup_loader / "loader.dll").resolve()),
                        "module_file": str(
                            (payload_dir / payload_current / "callback.dll").resolve()
                        ),
                    }
                )
                + "\n",
                encoding="utf-8",
            )
        if registry_loader is not None:
            (self.build / "blend_callback_protk.dat").write_text(
                f"name test\nstartup dll\nexec_file "
                f"{(loader_dir / registry_loader / 'loader.dll').resolve()}\nend\n",
                encoding="utf-8",
            )


def _healthy_build(root: Path, *, third_generation: bool = False) -> _Build:
    tree = _Build(root)
    payload_a = tree.payload(b"payload a")
    payload_b = tree.payload(b"payload b")
    tree.generation("a" * 64, payload_a)
    tree.generation("b" * 64, payload_b)
    if third_generation:
        tree.generation("c" * 64, payload_b)
        tree.records("a" * 64, Path("a" * 64), Path("a" * 64), payload_a)
    else:
        tree.records("a" * 64, Path("a" * 64), Path("a" * 64), payload_a)
    return tree


class GenerationInventoryTest(unittest.TestCase):
    def test_healthy_old_generation_is_candidate(self):
        import tempfile

        with tempfile.TemporaryDirectory() as name:
            tree = _healthy_build(Path(name))
            result = generation_inventory(tree.build)
            self.assertTrue(result["records_definitive"])
            self.assertFalse(result["record_conflict"])
            self.assertEqual(result["current_generation_key"], "a" * 64)
            self.assertEqual(result["reclaim_candidates"], ["b" * 64])
            self.assertEqual(result["needs_review"], [])
            # payload b is still referenced by the old loader generation, so
            # neither payload is a candidate or under review.
            self.assertEqual(result["reclaim_candidates_payload"], [])
            self.assertEqual(result["needs_review_payload"], [])

    def test_missing_build_stamp_keeps_generations(self):
        import tempfile

        with tempfile.TemporaryDirectory() as name:
            tree = _healthy_build(Path(name))
            (tree.build / "blend_loader_build.json").unlink()
            result = generation_inventory(tree.build)
            self.assertEqual(result["records_status"]["build_stamp"], "missing")
            self.assertFalse(result["records_definitive"])
            self.assertEqual(result["reclaim_candidates"], [])
            self.assertEqual(sorted(result["needs_review"]), ["a" * 64, "b" * 64])
            self.assertIn(
                "build_stamp_missing",
                result["generations"][0]["review_reasons"],
            )

    def test_corrupt_setup_keeps_generations(self):
        import tempfile

        with tempfile.TemporaryDirectory() as name:
            tree = _healthy_build(Path(name))
            (tree.build / "blend_callback_setup.json").write_text("{", encoding="utf-8")
            result = generation_inventory(tree.build)
            self.assertEqual(result["records_status"]["setup"], "corrupt")
            self.assertEqual(result["reclaim_candidates"], [])
            self.assertEqual(sorted(result["needs_review"]), ["a" * 64, "b" * 64])
            # Both payloads stay referenced by surviving loader generations
            # (which are themselves under review), so no payload is a candidate.
            self.assertEqual(result["reclaim_candidates_payload"], [])
            self.assertEqual(result["needs_review_payload"], [])

    def test_record_conflict_keeps_involved_generations(self):
        import tempfile

        with tempfile.TemporaryDirectory() as name:
            tree = _healthy_build(Path(name), third_generation=True)
            # Registry points at a different generation than the setup.
            tree.records("a" * 64, Path("a" * 64), Path("b" * 64), tree.payload_keys[0])
            result = generation_inventory(tree.build)
            self.assertTrue(result["record_conflict"])
            self.assertEqual(sorted(result["conflict_generations"]), ["a" * 64, "b" * 64])
            self.assertEqual(result["reclaim_candidates"], ["c" * 64])
            self.assertEqual(sorted(result["needs_review"]), ["a" * 64, "b" * 64])

    def test_missing_deployment_needs_review(self):
        import tempfile

        with tempfile.TemporaryDirectory() as name:
            tree = _healthy_build(Path(name))
            (tree.build / "blend_loader" / ("b" * 64) / "deployment.json").unlink()
            result = generation_inventory(tree.build)
            self.assertEqual(result["reclaim_candidates"], [])
            self.assertEqual(result["needs_review"], ["b" * 64])
            reasons = result["generations"][1]["review_reasons"]
            self.assertIn("deployment_missing", reasons)

    def test_recent_ready_file_is_runtime_evidence(self):
        import tempfile

        with tempfile.TemporaryDirectory() as name:
            tree = _healthy_build(Path(name))
            tree.generation("b" * 64, _digest_bytes(b"payload b"), ready_age_seconds=60)
            result = generation_inventory(tree.build)
            entry = result["generations"][1]
            self.assertIn("recent_ready_file", entry["runtime_evidence"])
            self.assertTrue(entry["referenced"])
            self.assertEqual(result["reclaim_candidates"], [])
            self.assertEqual(result["needs_review"], [])

    def test_probe_ready_marks_setup_generation(self):
        import tempfile

        with tempfile.TemporaryDirectory() as name:
            tree = _healthy_build(Path(name))
            result = generation_inventory(tree.build, probe_readiness="ready")
            entry = result["generations"][0]
            self.assertEqual(entry["generation_key"], "a" * 64)
            self.assertIn("probe_ready", entry["runtime_evidence"])
            self.assertEqual(result["runtime_probe"]["running_generation"], "a" * 64)

    def test_payload_mismatch_needs_review(self):
        import tempfile

        with tempfile.TemporaryDirectory() as name:
            tree = _healthy_build(Path(name))
            payload_key = tree.payload(b"tampered later")
            directory = tree.build / "blend_callback" / payload_key
            (directory / "callback.dll").write_bytes(b"different bytes")
            result = generation_inventory(tree.build)
            self.assertIn(payload_key, result["needs_review_payload"])
            entry = next(
                item
                for item in result["payload_generations"]
                if item["payload_sha256"] == payload_key
            )
            self.assertIn("callback_dll_mismatch", entry["review_reasons"])

    def test_unreferenced_payload_is_candidate(self):
        import tempfile

        with tempfile.TemporaryDirectory() as name:
            tree = _healthy_build(Path(name))
            orphan = tree.payload(b"orphan payload")
            result = generation_inventory(tree.build)
            self.assertEqual(result["reclaim_candidates_payload"], [orphan])


if __name__ == "__main__":
    unittest.main()
