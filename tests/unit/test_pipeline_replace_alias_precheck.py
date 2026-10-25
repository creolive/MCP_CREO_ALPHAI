"""FEAT-008/012: existing-alias pre-check for the pipeline snapshot refresh (offline).

Live evidence (build/assembly_pipeline_live_20261025T162553Z6eec525a, guard
build/guarded_live_20261025T162020624286, child_1.log): the pipeline driver
submitted ONE execute_plan carrying
[remove_component component='plate_a', assemble_component label='plate_a']
and the entry refused it with "Feature labels already exist: ['plate_a']" —
no job was created. Reusing an existing assemble label inside one plan is
therefore refused even when the same plan removes that label first; that is
the current production contract, and these tests pin it instead of asking
production to change. The fixed driver (tools/test_assembly_pipeline.py)
removes the stale label and re-assembles under a NEW unique label
(plate_a_refreshed), same source_model_id and original pose, in one atomic
job. Users who must keep the old label run TWO jobs — remove (revision+1),
then assemble (revision+1) — and a failure of the second job never undoes
the first.

Both scenarios run through the REAL generic_bridge.submit entry pre-check:
a temp model registry with real-style 32-hex model ids, managed output
layout and component aliases, native runner subprocess mocked (queued only,
never executed), no MCP server and no Creo involved.
"""

from __future__ import annotations

import copy
import hashlib
import tempfile
import unittest
import uuid
from contextlib import ExitStack
from pathlib import Path
from unittest.mock import patch

import bridge
import generic_bridge as general
from creo_mechdog import model_registry
from tools.test_assembly_pipeline import (
    REFRESHED_PLATE_A_LABEL,
    replace_operations,
)

IDENTITY3 = [[1, 0, 0], [0, 1, 0], [0, 0, 1]]
PLATE_A_FEATURE_ID = 40
# Real-style cross-API display names from the 2026-10-25 guarded runs: the
# list_components copy name and the session-assembly name of ONE occurrence.
LIST_COPY_NAME = "▩C_A3C874E18A0445A10001"
SESSION_NAME = "C_A3C874E18A0445A1_0"


def plate_a_pose(source_model_id: str) -> dict:
    """The rebuild pose of the stale plate_a snapshot (original frozen pose)."""
    return {
        "op": "assemble_component",
        "label": "plate_a",
        "source_model_id": source_model_id,
        "translation": [0, 0, 0],
        "rotation_matrix": IDENTITY3,
        "placement": "fixed",
    }


class ExistingAliasPrecheck(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory(prefix="feat008_replace_precheck_")
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name).resolve()
        (self.root / "jobs").mkdir()
        (self.root / "models").mkdir()
        # The assembly template lookup only needs an existing file.
        template = self.root / "creo" / "Common Files" / "templates"
        template.mkdir(parents=True)
        (template / "mmns_asm_design_abs.asm").write_bytes(b"template bytes")
        stack = ExitStack()
        self.addCleanup(stack.close)
        for obj, name, value in (
            (bridge, "ROOT", self.root),
            (bridge, "JOBS", self.root / "jobs"),
            (general, "MODELS", self.root / "models"),
        ):
            stack.enter_context(patch.object(obj, name, value))
        stack.enter_context(
            patch.object(bridge, "config", return_value={"creo_root": str(self.root / "creo")})
        )
        self.popen = stack.enter_context(patch.object(general.subprocess, "Popen"))

        # Real-style managed models: owned output naming, recorded baseline
        # identity, ready status, component aliases exactly as list_components
        # freezes them (op/feature_id/source_model_id/source_revision).
        self.source_id = uuid.uuid4().hex
        self._write_part(self.source_id, "pipe_src_a_fixture01")
        self.assembly_id = uuid.uuid4().hex
        self.assembly_revision = 2
        self._write_assembly()

    def _write_part(self, model_id: str, model_name: str) -> None:
        path = general.model_path(model_id)
        output = path / "output"
        output.mkdir(parents=True)
        part = output / f"{model_name}.prt.1"
        part.write_bytes(b"verified native part bytes")
        model = {
            "model_id": model_id,
            "model_name": model_name,
            "revision": 1,
            "status": "ready",
            "model_type": "part",
            "aliases": {},
            "inspection": {"components": []},
            "part_file": str(part),
            "part_sha256": hashlib.sha256(part.read_bytes()).hexdigest(),
            "output_directory": str(output),
        }
        model_registry.write_model(path, model)

    def _write_assembly(self) -> None:
        path = general.model_path(self.assembly_id)
        output = path / "output"
        output.mkdir(parents=True)
        part = output / "pipe_rebuilt_asm_fixture01.asm.1"
        part.write_bytes(b"verified native assembly bytes")
        model = {
            "model_id": self.assembly_id,
            "model_name": "pipe_rebuilt_asm_fixture01",
            "revision": self.assembly_revision,
            "status": "ready",
            "model_type": "assembly",
            "aliases": {
                "plate_a": {
                    "op": "assemble_component",
                    "feature_id": PLATE_A_FEATURE_ID,
                    "source_model_id": self.source_id,
                    "source_revision": 1,
                },
                "plate_b": {
                    "op": "assemble_component",
                    "feature_id": 41,
                    "source_model_id": "b" * 32,
                    "source_revision": 2,
                },
                "plate_b_second": {
                    "op": "assemble_component",
                    "feature_id": 42,
                    "source_model_id": "b" * 32,
                    "source_revision": 2,
                },
            },
            "inspection": {
                "components": [
                    {
                        "feature_id": PLATE_A_FEATURE_ID,
                        "model_name": LIST_COPY_NAME,
                        "transform": [[1, 0, 0, 0], [0, 1, 0, 0], [0, 0, 1, 0], [0, 0, 0, 1]],
                        "constraints": [{"type": 13, "type_name": "fix"}],
                    },
                    {"feature_id": 41, "model_name": SESSION_NAME},
                    {"feature_id": 42, "model_name": SESSION_NAME},
                ]
            },
            "part_file": str(part),
            "part_sha256": hashlib.sha256(part.read_bytes()).hexdigest(),
            "output_directory": str(output),
        }
        model_registry.write_model(path, model)

    def test_original_plan_reusing_existing_label_is_refused_before_any_job(self):
        """Offline reproduction of assembly_pipeline_live_20261025T162553Z
        step 9e: remove 'plate_a' + re-assemble label 'plate_a' in ONE plan is
        refused by the entry against the existing aliases, even though the
        same plan removes the label first."""
        stale_plan = [
            {"op": "remove_component", "component": "plate_a"},
            plate_a_pose(self.source_id),
        ]
        with self.assertRaisesRegex(ValueError, r"Feature labels already exist: \['plate_a'\]"):
            general.submit(
                copy.deepcopy(stale_plan),
                model_id=self.assembly_id,
                expected_revision=self.assembly_revision,
            )
        # Refusal happens before any job exists: nothing queued, no runner
        # spawned, model reservation untouched.
        self.popen.assert_not_called()
        self.assertEqual(list((self.root / "jobs").iterdir()), [])
        self.assertNotIn("pending_job", general.model_info(self.assembly_id))

    def test_new_label_replace_passes_the_real_precheck_and_queues(self):
        """The fixed driver plan (remove stale label + assemble under the NEW
        unique label, same source_model_id and original pose) passes the real
        generic_bridge entry pre-check in the SAME existing-alias environment
        and queues exactly one job."""
        fixed_plan = replace_operations(plate_a_pose(self.source_id))
        self.assertEqual(fixed_plan[1]["label"], REFRESHED_PLATE_A_LABEL)
        manifest = general.submit(
            copy.deepcopy(fixed_plan),
            model_id=self.assembly_id,
            expected_revision=self.assembly_revision,
        )
        self.assertEqual(manifest["status"], "queued")
        self.assertEqual(manifest["model_id"], self.assembly_id)
        self.assertEqual(manifest["revision"], self.assembly_revision)
        # The native runner is only spawned, never executed in this offline
        # test (no real server, no Creo): exactly one queueing Popen.
        self.popen.assert_called_once()
        self.assertIn("run-job", self.popen.call_args.args[0])

        directory = bridge.job_path(manifest["job_id"])
        request = bridge.read_json(directory / "request.json")
        operations = request["operations"]
        self.assertEqual(operations[0], {"op": "remove_component", "component": "plate_a"})
        reassemble = operations[1]
        self.assertEqual(reassemble["label"], REFRESHED_PLATE_A_LABEL)
        self.assertEqual(reassemble["source_model_id"], self.source_id)
        self.assertEqual(reassemble["translation"], [0, 0, 0])
        self.assertEqual(reassemble["rotation_matrix"], IDENTITY3)
        # The queued request references the real source component graph.
        self.assertIn(self.source_id, request["components"])
        # The model is reserved for the accepted job.
        self.assertEqual(general.model_info(self.assembly_id)["pending_job"], manifest["job_id"])
        queued = bridge.read_json(directory / "job.json")
        self.assertEqual(queued["status"], "queued")

    def test_plain_reassemble_of_existing_label_is_refused_too(self):
        """The pre-check is not specific to the remove+assemble pair: any plan
        carrying an assemble label that already exists is refused."""
        with self.assertRaisesRegex(ValueError, r"Feature labels already exist: \['plate_b'\]"):
            general.submit(
                [
                    {
                        "op": "assemble_component",
                        "label": "plate_b",
                        "source_model_id": self.source_id,
                        "translation": [5, 0, 0],
                        "placement": "fixed",
                    }
                ],
                model_id=self.assembly_id,
                expected_revision=self.assembly_revision,
            )
        self.popen.assert_not_called()


if __name__ == "__main__":
    unittest.main()
