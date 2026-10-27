"""DEV-047 T09: assembly constraint snapshot replay planning."""

from __future__ import annotations

import copy
import hashlib
import json
import tempfile
import time
import unittest
from contextlib import ExitStack
from pathlib import Path
from unittest.mock import patch

import bridge
import generic_bridge as general
from creo_mechdog import assembly_replay
from creo_mechdog.schema import validate_operations

ROOT = Path(__file__).resolve().parents[2]
NATIVE = ROOT / "native"
SNAPSHOT_ID = "1" * 32
SOURCE_A = "a" * 32
SOURCE_B = "b" * 32

IDENTITY = [[1.0, 0.0, 0.0, 0.0], [0.0, 1.0, 0.0, 0.0], [0.0, 0.0, 1.0, 0.0], [0.0, 0.0, 0.0, 1.0]]
TRANSLATED = [
    [1.0, 0.0, 0.0, 0.0],
    [0.0, 1.0, 0.0, 0.0],
    [0.0, 0.0, 1.0, 0.0],
    [20.0, 0.0, 0.0, 1.0],
]
SCALED = [[2.0, 0.0, 0.0, 0.0], [0.0, 2.0, 0.0, 0.0], [0.0, 0.0, 2.0, 0.0], [0.0, 0.0, 0.0, 1.0]]
UNIT = {
    "name": "mm",
    "query_code": 0,
    "scale_to_mm": 1.0,
    "scale_to_mm_known": True,
    "scale_query_codes": {"unit": 0, "mm_unit": 0, "conversion": 0},
}


def reference(owner: str | None, item_type: int, item_id: int) -> dict:
    item = {"item_type": item_type, "item_id": item_id, "item_query_code": 0}
    if owner is None:
        item.update(owner_scope="assembly", occurrence_path=[])
    else:
        item.update(
            owner_scope="component",
            occurrence_path=[abs(hash(owner)) % 1000 + 1],
            occurrence_component_id=abs(hash(owner)) % 1000 + 1,
            occurrence_label=owner,
            occurrence_label_query_code=0,
        )
    return item


def constraint(
    ctype: str,
    asm: dict,
    comp: dict,
    *,
    offset_mm: float | None = 0.0,
    asm_side: str = "yellow",
    comp_side: str = "yellow",
    replayable: bool = True,
    reason: str | None = None,
    placement_kind: str | None = None,
) -> dict:
    item = {
        "type": ctype,
        "offset": offset_mm,
        "offset_mm": offset_mm,
        "offset_unit": UNIT,
        "asm_reference": asm,
        "comp_reference": comp,
        "asm_side": asm_side,
        "comp_side": comp_side,
        "orientation": comp_side,
        "replayable": replayable,
        "reason": reason,
        "query_codes": {"type": 0, "offset": 0, "asm_reference": 0, "comp_reference": 0},
    }
    if placement_kind is not None:
        item["placement_kind"] = placement_kind
    return item


def component(
    label: str,
    component_id: int,
    *,
    constraints: list[dict] | None = None,
    matrix: list[list[float]] | None = None,
    depth: int = 0,
    **overrides,
) -> dict:
    path = [component_id] if depth == 0 else [component_id - 1, component_id]
    item = {
        "component_id": component_id,
        "occurrence_path": path,
        "parent_path": path[:-1],
        "depth": depth,
        "occurrence_label": label,
        "occurrence_label_query_code": 0,
        "feature_status": 0,
        "suppressed": False,
        "packaged": False,
        "resolved": True,
        "name": f"{label}.prt",
        "model_type": "part",
        "transform_to_parent": matrix or IDENTITY,
        "transform_mm_known": True,
        "constraints": constraints or [],
        "query_codes": {"transform": 0, "model": 0, "constraints": 0},
    }
    item.update(overrides)
    return item


def snapshot(components: list[dict], **overrides) -> dict:
    value = {
        "schema_version": 3,
        "created": time.time(),
        "checked_at": "2026-10-26T12:00:00+08:00",
        "session_fingerprint": "fixture-session",
        "assembly": {"name": "source_asm", "length_unit": UNIT},
        "components": components,
        "complete": True,
        "incomplete": False,
        "truncated": False,
        "depth_limited": False,
        "root_visit_code": 0,
    }
    value.update(overrides)
    return value


def fixed(label: str, component_id: int, **overrides) -> dict:
    return component(
        label,
        component_id,
        constraints=[constraint("fix", None, None, offset_mm=None, placement_kind="fixed")],
        **overrides,
    )


def default_placed(label: str, component_id: int, **overrides) -> dict:
    return component(
        label,
        component_id,
        constraints=[constraint("default", None, None, offset_mm=None, placement_kind="default")],
        **overrides,
    )


def pins() -> list[dict]:
    """base is fixed; pin carries one of each supported constraint."""
    base = fixed("base", 5)
    pin = component(
        "pin",
        6,
        matrix=TRANSLATED,
        constraints=[
            constraint("mate", reference("base", 22, 41), reference("pin", 22, 42)),
            constraint(
                "align",
                reference("base", 22, 43),
                reference("pin", 22, 44),
                asm_side="red",
                comp_side="red",
            ),
            constraint(
                "mate_offset",
                reference("base", 22, 45),
                reference("pin", 22, 46),
                offset_mm=12.5,
            ),
            constraint(
                "align_offset",
                reference("base", 22, 47),
                reference("pin", 22, 48),
                offset_mm=-3.25,
            ),
            constraint("insert", reference("base", 23, 51), reference("pin", 23, 52)),
            constraint("csys", reference(None, 24, 61), reference("pin", 24, 62)),
        ],
    )
    return [base, pin]


def mappings(nodes: list[dict], sources: dict[str, str] | None = None) -> list[dict]:
    sources = sources or {}
    return [
        {
            "occurrence": node["occurrence_label"],
            "label": f"t_{node['occurrence_label']}",
            "source_model_id": sources.get(node["occurrence_label"], SOURCE_A),
        }
        for node in nodes
    ]


def references() -> list[dict]:
    items = []
    for owner, item_type, item_id in (
        ("base", 22, 41),
        ("pin", 22, 42),
        ("base", 22, 43),
        ("pin", 22, 44),
        ("base", 22, 45),
        ("pin", 22, 46),
        ("base", 22, 47),
        ("pin", 22, 48),
        ("base", 23, 51),
        ("pin", 23, 52),
        ("pin", 24, 62),
    ):
        items.append(
            {
                "source": {"component": owner, "item_type": item_type, "item_id": item_id},
                "target": {"kind": "surface", "id": item_id + 100},
            }
        )
    items.append(
        {
            "source": {"component": None, "item_type": 24, "item_id": 61},
            "target": {"kind": "default_csys"},
        }
    )
    return items


class ReplayFixture(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory(prefix="t09_replay_")
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        (self.root / "jobs").mkdir()
        (self.root / "models").mkdir()
        stack = ExitStack()
        self.addCleanup(stack.close)
        stack.enter_context(patch.object(bridge, "ROOT", self.root))
        stack.enter_context(patch.object(bridge, "JOBS", self.root / "jobs"))
        stack.enter_context(patch.object(general, "MODELS", self.root / "models"))

    def source(self, model_id: str, *, revision: int = 3, body: bytes = b"source-bytes") -> dict:
        output = self.root / "models" / model_id / "output"
        output.mkdir(parents=True, exist_ok=True)
        part = output / "part.prt"
        part.write_bytes(body)
        model = {
            "model_id": model_id,
            "model_name": "plate",
            "model_type": "part",
            "revision": revision,
            "status": "ready",
            "part_file": str(part),
            "part_sha256": hashlib.sha256(body).hexdigest(),
            "aliases": {},
        }
        (self.root / "models" / model_id / "model.json").write_text(
            json.dumps(model), encoding="utf-8"
        )
        return model

    def write_snapshot(self, value: dict, snapshot_id: str = SNAPSHOT_ID) -> Path:
        directory = self.root / "jobs" / snapshot_id
        directory.mkdir(parents=True, exist_ok=True)
        file = directory / "session_assembly.json"
        file.write_text(json.dumps(value), encoding="utf-8")
        return file

    def plan(self, value: dict, component_mapping: list[dict], reference_mapping: list[dict]):
        self.write_snapshot(value)
        return assembly_replay.plan_assembly_rebuild(
            SNAPSHOT_ID, component_mapping, reference_mapping
        )


class SnapshotEvidence(ReplayFixture):
    def test_new_snapshot_is_accepted_and_reports_schema_and_window(self):
        self.source(SOURCE_A)
        nodes = pins()
        result = self.plan(snapshot(nodes), mappings(nodes), references())
        self.assertTrue(result["read_only"])
        self.assertEqual(result["snapshot"]["schema_version"], 3)
        self.assertLessEqual(result["snapshot"]["age_seconds"], 1)
        self.assertEqual(result["planning_window_seconds"], 600)
        self.assertNotIn("operation_results", result)
        self.assertIn("not a long-lived write", result["window_note"])

    def test_missing_older_and_expired_snapshots_are_refused(self):
        self.source(SOURCE_A)
        self.write_snapshot(snapshot(pins()))
        self.write_snapshot(snapshot(pins(), schema_version=2, created=time.time() - 10))
        with self.assertRaises(ValueError) as raised:
            assembly_replay.plan_assembly_rebuild(SNAPSHOT_ID, [], [])
        self.assertIn("older than the replay schema", str(raised.exception))
        no_version = snapshot(pins())
        no_version.pop("schema_version")
        self.write_snapshot(no_version)
        with self.assertRaises(ValueError) as raised:
            assembly_replay.plan_assembly_rebuild(SNAPSHOT_ID, [], [])
        self.assertIn("older service version", str(raised.exception))
        self.write_snapshot(snapshot(pins(), created=time.time() - 601))
        with self.assertRaises(ValueError) as raised:
            assembly_replay.plan_assembly_rebuild(SNAPSHOT_ID, [], [])
        self.assertIn("expired", str(raised.exception))

    def test_incomplete_and_nested_evidence_are_refused(self):
        self.source(SOURCE_A)
        for overrides, message in (
            ({"complete": False, "incomplete": True}, "incomplete"),
            ({"depth_limited": True}, "incomplete"),
            ({"truncated": True}, "incomplete"),
        ):
            with self.subTest(overrides=overrides):
                self.write_snapshot(snapshot(pins(), **overrides))
                with self.assertRaises(ValueError) as raised:
                    assembly_replay.plan_assembly_rebuild(SNAPSHOT_ID, [], [])
                self.assertIn(message, str(raised.exception))
        nested = component("sub", 9, depth=1)
        self.write_snapshot(snapshot([nested]))
        with self.assertRaises(ValueError) as raised:
            assembly_replay.plan_assembly_rebuild(
                SNAPSHOT_ID,
                [{"occurrence": "sub", "label": "t_sub", "source_model_id": SOURCE_A}],
                [],
            )
        self.assertIn("nested", str(raised.exception))

    def test_snapshot_id_and_file_validation(self):
        for snapshot_id in ("", "nothex", "A" * 32):
            with self.subTest(snapshot_id=snapshot_id):
                with self.assertRaises(ValueError):
                    assembly_replay.plan_assembly_rebuild(snapshot_id, [], [])
        with patch.object(
            bridge, "job_path", side_effect=ValueError("Job directories cannot be links")
        ):
            with self.assertRaises(ValueError):
                assembly_replay.plan_assembly_rebuild(SNAPSHOT_ID, [], [])


class OperationPlan(ReplayFixture):
    def test_six_constraint_types_insert_first_then_constrain(self):
        self.source(SOURCE_A)
        nodes = pins()
        result = self.plan(snapshot(nodes), mappings(nodes), references())
        operations = result["operations"]
        self.assertEqual(
            [op["op"] for op in operations],
            ["assemble_component"] * 2 + ["component_constraints"],
        )
        self.assertEqual(result["operation_count"], 3)
        for operation in operations[:2]:
            self.assertEqual(operation["placement"], "fixed")
            self.assertEqual(operation["constraints"], [])
            self.assertEqual(operation["rebuild_binding"]["source_revision"], 3)
            for key in ("source_model_id", "source_part_sha256"):
                self.assertTrue(operation["rebuild_binding"][key])
        self.assertEqual(operations[0]["label"], "t_base")
        self.assertEqual(operations[1]["label"], "t_pin")
        self.assertEqual(operations[1]["translation"], [20.0, 0.0, 0.0])
        self.assertEqual(operations[1]["rotation_matrix"], [row[:3] for row in IDENTITY[:3]])
        expected = [
            ("mate", 0.0, "yellow", "yellow", "t_base"),
            ("align", 0.0, "red", "red", "t_base"),
            ("mate_offset", 12.5, "yellow", "yellow", "t_base"),
            ("align_offset", -3.25, "yellow", "yellow", "t_base"),
            ("insert", 0.0, "yellow", "yellow", "t_base"),
            ("csys", 0.0, "yellow", "yellow", None),
        ]
        (operation,) = operations[2:]
        self.assertEqual(operation["op"], "component_constraints")
        self.assertEqual(operation["component"], "t_pin")
        self.assertEqual(len(operation["constraints"]), 6)
        for row, (ctype, offset, asm_side, comp_side, sibling) in zip(
            operation["constraints"], expected, strict=True
        ):
            self.assertEqual(row["type"], ctype)
            self.assertEqual(row["offset"], offset)
            self.assertEqual(row["assembly_side"], asm_side)
            self.assertEqual(row["component_side"], comp_side)
            if sibling is None:
                self.assertNotIn("assembly_component", row)
            else:
                self.assertEqual(row["assembly_component"], sibling)
        validate_operations(operations)

    def test_fixed_and_default_placements_stay_single_placement_operations(self):
        self.source(SOURCE_A)
        nodes = [fixed("base", 5), default_placed("lid", 7)]
        result = self.plan(snapshot(nodes), mappings(nodes), [])
        self.assertEqual(
            [op["op"] for op in result["operations"]],
            ["assemble_component", "assemble_component"],
        )
        self.assertEqual(result["operations"][0]["placement"], "fixed")
        self.assertEqual(result["operations"][1]["placement"], "default")
        modes = {item["occurrence"]: item for item in result["placements"]}
        self.assertEqual(modes["base"]["mode"], "fixed")
        self.assertEqual(modes["lid"]["mode"], "default")
        self.assertEqual(modes["base"]["constraint_count"], 0)
        self.assertEqual(modes["lid"]["constraint_count"], 0)
        self.assertIsNone(modes["base"]["intermediate_placement"])

    def test_unconstrained_component_is_frozen_explicitly(self):
        self.source(SOURCE_A)
        nodes = [component("loose", 8)]
        result = self.plan(snapshot(nodes), mappings(nodes), [])
        self.assertEqual(result["operations"][0]["placement"], "fixed")
        self.assertEqual(result["placements"][0]["mode"], "fixed")
        self.assertEqual(result["placements"][0]["source_placement"], "unconstrained")
        nodes[0]["packaged"] = True
        result = self.plan(snapshot(nodes), mappings(nodes), [])
        self.assertEqual(result["placements"][0]["source_placement"], "packaged")

    def test_plan_has_no_job_or_toolkit_side_effect(self):
        self.source(SOURCE_A)
        nodes = pins()
        with patch.object(bridge, "toolkit_lock", side_effect=AssertionError("no Toolkit")):
            result = self.plan(snapshot(nodes), mappings(nodes), references())
        directory = self.root / "jobs" / SNAPSHOT_ID
        self.assertEqual([path.name for path in directory.iterdir()], ["session_assembly.json"])
        self.assertNotIn("operation_results", result)
        self.assertNotIn("job_id", result)

    def test_over_two_hundred_operations_is_refused_without_splitting(self):
        self.source(SOURCE_A)
        nodes = [fixed(f"c{index}", index + 1) for index in range(201)]
        with self.assertRaises(ValueError) as raised:
            self.plan(snapshot(nodes), mappings(nodes), [])
        message = str(raised.exception)
        self.assertIn("201 operations", message)
        self.assertIn("at most 200", message)
        self.assertIn("instead of being split", message)


class MappingAdmission(ReplayFixture):
    def test_missing_component_mapping_names_the_occurrence(self):
        self.source(SOURCE_A)
        nodes = pins()
        with self.assertRaises(ValueError) as raised:
            self.plan(snapshot(nodes), mappings(nodes)[:1], references())
        self.assertIn("component_mapping is incomplete", str(raised.exception))
        self.assertIn("pin", str(raised.exception))

    def test_occurrence_by_path_resolves_repeated_labels(self):
        self.source(SOURCE_A)
        nodes = [component("pin", 6), component("pin", 7)]
        with self.assertRaises(ValueError) as raised:
            self.plan(snapshot(nodes), mappings(nodes), [])
        self.assertIn("ambiguous", str(raised.exception))
        mapping = [
            {"occurrence": [6], "label": "t_pin_a", "source_model_id": SOURCE_A},
            {"occurrence": [7], "label": "t_pin_b", "source_model_id": SOURCE_A},
        ]
        result = self.plan(snapshot(nodes), mapping, [])
        self.assertEqual([op["label"] for op in result["operations"]], ["t_pin_a", "t_pin_b"])

    def test_bad_component_mapping_fields_are_refused(self):
        self.source(SOURCE_A)
        nodes = [fixed("base", 5)]
        cases = [
            ([{"occurrence": "base", "label": "Base", "source_model_id": SOURCE_A}], "lowercase"),
            (
                [{"occurrence": "base", "label": "t_base", "source_model_id": "nope"}],
                "32 lowercase",
            ),
            (
                [{"occurrence": "ghost", "label": "t_base", "source_model_id": SOURCE_A}],
                "does not match",
            ),
            (
                [
                    {"occurrence": "base", "label": "t_base", "source_model_id": SOURCE_A},
                    {"occurrence": "base", "label": "t_two", "source_model_id": SOURCE_A},
                ],
                "already maps",
            ),
            (
                [
                    {"occurrence": "base", "label": "t_base", "source_model_id": SOURCE_A},
                    {"occurrence": "base", "label": "t_base", "source_model_id": SOURCE_A},
                ],
                "already maps",
            ),
            ([{"occurrence": "base", "label": "t_base"}], "missing required field"),
            (
                [{"occurrence": "base", "label": "t_base", "source_model_id": SOURCE_A, "x": 1}],
                "unknown fields",
            ),
        ]
        for mapping, message in cases:
            with self.subTest(message=message):
                with self.assertRaises(ValueError) as raised:
                    self.plan(snapshot(nodes), mapping, [])
                self.assertIn(message, str(raised.exception))

    def test_duplicate_target_labels_are_refused(self):
        self.source(SOURCE_A)
        nodes = [fixed("base", 5), fixed("lid", 6)]
        mapping = [
            {"occurrence": "base", "label": "t_same", "source_model_id": SOURCE_A},
            {"occurrence": "lid", "label": "t_same", "source_model_id": SOURCE_A},
        ]
        with self.assertRaises(ValueError) as raised:
            self.plan(snapshot(nodes), mapping, [])
        self.assertIn("must be unique", str(raised.exception))

    def test_source_must_be_ready_part_with_recorded_digest(self):
        self.source(SOURCE_A)
        nodes = [fixed("base", 5)]
        mapping = mappings(nodes)
        path = self.root / "models" / SOURCE_A / "model.json"
        original = json.loads(path.read_text(encoding="utf-8"))
        for overrides, message in (
            ({"model_type": "assembly"}, "part/sheetmetal"),
            ({"status": "failed"}, "not ready"),
            ({"revision": 0}, "saved revision"),
            ({"part_sha256": "0" * 64}, "bytes changed"),
        ):
            with self.subTest(overrides=overrides):
                path.write_text(json.dumps({**original, **overrides}), encoding="utf-8")
                with self.assertRaises(ValueError) as raised:
                    self.plan(snapshot(nodes), mapping, [])
                self.assertIn(message, str(raised.exception))

    def test_transform_must_be_a_rigid_millimeter_pose(self):
        self.source(SOURCE_A)
        nodes = [fixed("base", 5, matrix=SCALED)]
        with self.assertRaises(ValueError) as raised:
            self.plan(snapshot(nodes), mappings(nodes), [])
        self.assertIn("orthonormal", str(raised.exception))
        nodes = [fixed("base", 5, matrix=None, transform_mm_known=False)]
        nodes[0]["transform_to_parent"] = None
        with self.assertRaises(ValueError) as raised:
            self.plan(snapshot(nodes), mappings(nodes), [])
        self.assertIn("known millimeter source transform", str(raised.exception))


class ConstraintAdmission(ReplayFixture):
    def build(self, constraints: list[dict], references_: list[dict] | None = None):
        self.source(SOURCE_A)
        nodes = [fixed("base", 5), component("pin", 6, constraints=constraints)]
        return self.plan(snapshot(nodes), mappings(nodes), references_ or references())

    def test_unknown_constraint_type_is_refused(self):
        with self.assertRaises(ValueError) as raised:
            self.build([constraint("tangent", reference("base", 22, 41), reference("pin", 22, 42))])
        self.assertIn("unsupported constraint type 'tangent'", str(raised.exception))

    def test_unreplayable_constraint_reason_is_reported(self):
        with self.assertRaises(ValueError) as raised:
            self.build(
                [
                    constraint(
                        "mate_offset",
                        reference("base", 22, 45),
                        reference("pin", 22, 46),
                        replayable=False,
                        reason="offset_unit_unknown",
                    )
                ]
            )
        self.assertIn("not replayable (offset_unit_unknown)", str(raised.exception))

    def test_automatic_and_mixed_placements_are_refused(self):
        with self.assertRaises(ValueError) as raised:
            self.build([constraint("auto", None, None, placement_kind="auto")])
        self.assertIn("automatic placement", str(raised.exception))
        with self.assertRaises(ValueError) as raised:
            self.build(
                [
                    constraint("fix", None, None, placement_kind="fixed"),
                    constraint("mate", reference("base", 22, 41), reference("pin", 22, 42)),
                ]
            )
        self.assertIn("mixes a fixed/default placement", str(raised.exception))

    def test_missing_reference_mapping_names_the_source_reference(self):
        with self.assertRaises(ValueError) as raised:
            self.build(
                [constraint("mate", reference("base", 22, 41), reference("pin", 22, 42))],
                references_=[
                    {
                        "source": {"component": "pin", "item_type": 22, "item_id": 42},
                        "target": {"kind": "surface", "id": 142},
                    }
                ],
            )
        message = str(raised.exception)
        self.assertIn("no entry for the sibling 'base' reference", message)
        self.assertIn("item_type=22, item_id=41", message)

    def test_unreplayable_root_reference_is_named(self):
        with self.assertRaises(ValueError) as raised:
            self.build(
                [constraint("csys", reference(None, 24, 61), reference("pin", 24, 62))],
                references_=[
                    {
                        "source": {"component": "pin", "item_type": 24, "item_id": 62},
                        "target": {"kind": "default_csys"},
                    }
                ],
            )
        self.assertIn("no entry for the root reference", str(raised.exception))

    def test_ambiguous_reference_mapping_is_refused(self):
        entries = references()
        ambiguous = copy.deepcopy(entries[0])
        ambiguous["source"]["side"] = "yellow"
        entries.append(ambiguous)
        with self.assertRaises(ValueError) as raised:
            self.build(
                [constraint("mate", reference("base", 22, 41), reference("pin", 22, 42))], entries
            )
        self.assertIn("several entries", str(raised.exception))

    def test_reference_mapping_fields_are_validated(self):
        cases = [
            (
                {
                    "source": {"component": "base", "item_type": "22", "item_id": 41},
                    "target": {"kind": "surface", "id": 1},
                },
                "integer item_type",
            ),
            (
                {"source": {"component": "base", "item_type": 22, "item_id": 41}, "target": {}},
                "with kind",
            ),
            (
                {
                    "source": {"component": "base", "item_type": 22, "item_id": 41},
                    "target": {"kind": "surface", "id": 1},
                    "side": "green",
                },
                "unknown fields",
            ),
            (
                {
                    "source": {
                        "component": "base",
                        "item_type": 22,
                        "item_id": 41,
                        "side": "green",
                    },
                    "target": {"kind": "surface", "id": 1},
                },
                "source.side",
            ),
        ]
        for entry, message in cases:
            with self.subTest(message=message):
                with self.assertRaises(ValueError) as raised:
                    self.build(
                        [constraint("mate", reference("base", 22, 41), reference("pin", 22, 42))],
                        [entry],
                    )
                self.assertIn(message, str(raised.exception))

    def test_target_component_must_be_planned(self):
        entries = references()
        for entry in entries:
            if entry["source"].get("component") == "base":
                entry["target_component"] = "t_missing"
        with self.assertRaises(ValueError) as raised:
            self.build(
                [constraint("mate", reference("base", 22, 41), reference("pin", 22, 42))], entries
            )
        self.assertIn("must name a planned target component", str(raised.exception))

    def test_component_side_cannot_name_another_component(self):
        entries = references()
        for entry in entries:
            if entry["source"].get("component") == "pin":
                entry["target_component"] = "t_base"
        with self.assertRaises(ValueError) as raised:
            self.build(
                [constraint("mate", reference("base", 22, 41), reference("pin", 22, 42))], entries
            )
        self.assertIn("not allowed on a component-side reference", str(raised.exception))


class BindingAdmission(ReplayFixture):
    def test_valid_binding_passes_and_reports_each_source(self):
        self.source(SOURCE_A)
        nodes = pins()
        result = self.plan(snapshot(nodes), mappings(nodes), references())
        assembly_replay.validate_source_bindings(
            result["operations"], models_root=self.root / "models"
        )
        self.assertEqual(len(result["source_bindings"]), 1)
        self.assertEqual(result["source_bindings"][0]["source_model_id"], SOURCE_A)
        self.assertEqual(result["source_bindings"][0]["source_revision"], 3)

    def assert_rejected(self, operations: list[dict], message: str):
        with self.assertRaises(ValueError) as raised:
            assembly_replay.validate_source_bindings(operations, models_root=self.root / "models")
        self.assertIn(message, str(raised.exception))

    def test_revision_digest_and_file_changes_are_refused(self):
        self.source(SOURCE_A)
        nodes = pins()
        result = self.plan(snapshot(nodes), mappings(nodes), references())
        operations = result["operations"]
        registry = self.root / "models" / SOURCE_A / "model.json"
        original = json.loads(registry.read_text(encoding="utf-8"))
        registry.write_text(json.dumps({**original, "revision": 4}), encoding="utf-8")
        self.assert_rejected(operations, "source revision changed after planning")
        registry.write_text(json.dumps({**original, "part_sha256": "0" * 64}), encoding="utf-8")
        self.assert_rejected(operations, "source file digest changed after planning")
        registry.write_text(json.dumps(original), encoding="utf-8")
        (self.root / "models" / SOURCE_A / "output" / "part.prt").write_bytes(b"edited-bytes")
        self.assert_rejected(operations, "bytes changed on disk after planning")
        (self.root / "models" / SOURCE_A / "output" / "part.prt").unlink()
        self.assert_rejected(operations, "saved file is missing")

    def test_binding_is_only_accepted_on_assemble_component(self):
        self.source(SOURCE_A)
        nodes = pins()
        result = self.plan(snapshot(nodes), mappings(nodes), references())
        operations = result["operations"]
        broken = copy.deepcopy(operations[2])
        broken["rebuild_binding"] = operations[1]["rebuild_binding"]
        self.assert_rejected([broken], "only accepted on assemble_component")
        mismatch = copy.deepcopy(operations[1])
        mismatch["rebuild_binding"]["source_model_id"] = SOURCE_B
        self.assert_rejected([mismatch], "does not match the operation")
        invalid = copy.deepcopy(operations[1])
        invalid["rebuild_binding"]["source_revision"] = 0
        self.assert_rejected([invalid], "positive integer")


class SchemaAndNativeGuards(ReplayFixture):
    def test_plan_operations_match_the_execute_plan_schema(self):
        self.source(SOURCE_A)
        nodes = pins()
        result = self.plan(snapshot(nodes), mappings(nodes), references())
        checked = validate_operations(result["operations"])
        self.assertEqual(len(checked), 3)
        self.assertTrue(checked[1]["rebuild_binding"]["source_part_sha256"])
        self.assertEqual(checked[2]["constraints"][0]["assembly_component"], "t_base")

    def test_assembly_component_and_side_contract(self):
        base = {
            "op": "component_constraints",
            "component": "pin",
            "constraints": [
                {
                    "type": "mate",
                    "assembly_reference": {"kind": "surface", "id": 1},
                    "component_reference": {"kind": "surface", "id": 2},
                    "assembly_component": "base",
                    "assembly_side": "none",
                    "component_side": "red",
                }
            ],
        }
        checked = validate_operations([base])
        row = checked[0]["constraints"][0]
        self.assertEqual(row["assembly_component"], "base")
        self.assertEqual(row["assembly_side"], "none")
        for bad in ("Base", "bad-label", -1, True, 3.5, ""):
            with self.subTest(bad=bad):
                with self.assertRaises(Exception):
                    validate_operations(
                        [
                            {
                                **base,
                                "constraints": [
                                    {
                                        **base["constraints"][0],
                                        "assembly_component": bad,
                                    }
                                ],
                            }
                        ]
                    )

    def test_native_replay_rules_are_present(self):
        advanced = (NATIVE / "advanced.cpp").read_text(encoding="utf-8")
        generic = (NATIVE / "generic.cpp").read_text(encoding="utf-8")
        self.assertIn("verify_rebuild_binding(op, source)", advanced)
        self.assertIn("Rebuild source revision changed after planning", advanced)
        self.assertIn("assembly_component must name a component of this assembly", advanced)
        self.assertIn('constraint_side(spec, "assembly_side")', advanced)
        self.assertIn('std::runtime_error("Unsupported assembly constraint type: "', advanced)
        for field in (
            'item["asm_side"]',
            'item["comp_side"]',
            'item["offset_unit"]',
            'item["offset_mm"]',
            'item["replayable"]',
            'item["reason"]',
            "occurrence_label_query_code",
            'reference["owner_scope"]',
            '"component_reference_not_own_component"',
            "component_label_json(",
        ):
            self.assertIn(field, generic)


if __name__ == "__main__":
    unittest.main()
