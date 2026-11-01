"""FEAT-052: assembly recolor by part family (offline unit tests).

Covers the plan acceptance items for input/grouping and preview/protocol:
automatic grouping by source_model_id, explicit family merging, multiple
labels with one consistent source, source conflicts (refused, with the
explicit-table escape hatch), duplicated/omitted components, invalid RGB
including booleans, stale revisions, non-assembly and missing-component
refusals; previews with no Toolkit call, no job and no revision change,
32 KiB pagination and stale cursors after registry/request/revision changes.
Native workers are substituted or refused on contact; no Creo is contacted.
"""

import hashlib
import json
import tempfile
import unittest
from contextlib import ExitStack
from pathlib import Path
from unittest.mock import patch

import bridge
import generic_bridge as general
from creo_mechdog import appearance
from creo_mechdog.model_queries import RESPONSE_BUDGET, decode_cursor, serialized_size
from creo_mechdog.schema import validate_operations
from tests.unit import test_adoption as fixture

ASSEMBLY_NAME = "wb_asm"
SRC_A = "1" * 32
SRC_B = "2" * 32
SRC_C = "3" * 32
MODEL_ID = "a" * 32


def part_appearance(state="absent", rgb=None, query_code=0):
    return {"state": state, "rgb": rgb, "query_code": query_code}


def component(feature_id, name, with_appearance=True):
    record = {
        "feature_id": feature_id,
        "model_name": name,
        "transform": [[1, 0, 0, 0], [0, 1, 0, 0], [0, 0, 1, 0], [0, 0, 0, 1]],
        "transform_source": "component_to_assembly",
        "packaged": False,
        "underconstrained": False,
        "constraints": [],
    }
    if with_appearance:
        record["appearance"] = part_appearance()
    return record


def alias(label, source_model_id, feature_id, source_revision=2):
    return {
        "op": "assemble_component",
        "feature_id": feature_id,
        "source_model_id": source_model_id,
        "source_revision": source_revision,
    }


def standard_records(with_appearance=True):
    return [
        component(40, "c_job_0", with_appearance),
        component(41, "c_job_1", with_appearance),
        component(42, "c_job_2", with_appearance),
    ]


def standard_aliases():
    return {
        "gear_a": alias("gear_a", SRC_A, 40),
        "gear_b": alias("gear_b", SRC_A, 41),
        "shaft_main": alias("shaft_main", SRC_B, 42),
    }


DRIVE_FAMILIES = {
    "gear_family": ["gear_a", "gear_b"],
    "shaft_family": ["shaft_main"],
}
DRIVE_PALETTE = {
    "gear_family": [0.9, 0.6, 0.1],
    "shaft_family": [0.2, 0.4, 0.8],
}


class AppearanceFixture(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory(prefix="appearance_")
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
        self.model_id = MODEL_ID

    def write_model(
        self,
        model_id=MODEL_ID,
        *,
        model_type="assembly",
        revision=3,
        records=None,
        aliases=None,
        with_part=True,
        status="ready",
        pending_job=None,
        recovery_pending=None,
        name=ASSEMBLY_NAME,
    ):
        records = standard_records() if records is None else records
        aliases = standard_aliases() if aliases is None else aliases
        model = {
            "model_id": model_id,
            "model_name": name,
            "model_type": model_type,
            "revision": revision,
            "created_at": "2026-11-01T00:00:00+00:00",
            "updated_at": "2026-11-01T00:00:00+00:00",
            "status": status,
            "aliases": aliases,
            "inspection": {
                "healthy": True,
                "model_type": model_type,
                "components": records,
                "counts": {"components": len(records)},
            },
            "output_directory": str(self.directory / "models" / model_id / "output"),
            "part_file": None,
        }
        if pending_job is not None:
            model["pending_job"] = pending_job
        if recovery_pending is not None:
            model["recovery_pending"] = recovery_pending
        output = self.directory / "models" / model_id / "output"
        output.mkdir(parents=True, exist_ok=True)
        if with_part:
            extension = "asm" if model_type == "assembly" else "prt"
            part = output / f"{name}.{extension}.1"
            part.write_bytes(b"fixture native model bytes")
            model["part_file"] = str(part)
            model["part_sha256"] = hashlib.sha256(part.read_bytes()).hexdigest()
        entry = self.directory / "models" / model_id / "model.json"
        entry.write_text(json.dumps(model), encoding="utf-8")
        return model

    def read_model(self, model_id=MODEL_ID):
        return json.loads(
            (self.directory / "models" / model_id / "model.json").read_text(encoding="utf-8")
        )

    def write_template_config(self):
        creo = self.directory / "creo"
        template = creo / "Common Files" / "templates" / "mmns_asm_design_abs.asm"
        template.parent.mkdir(parents=True, exist_ok=True)
        template.write_bytes(b"fixture assembly template")
        (self.directory / "config.json").write_text(
            json.dumps({"creo_root": str(creo), "vcvars64": str(self.directory / "vcvars.bat")}),
            encoding="utf-8",
        )


class GroupingAndInputRules(AppearanceFixture):
    """Plan acceptance: 输入与分组."""

    def test_automatic_grouping_by_source_model_id(self):
        self.write_model()
        page = appearance.preview_recolor(self.model_id, 3)
        self.assertEqual(page["mode"], "auto")
        self.assertEqual(page["families_total"], 2)
        self.assertEqual(page["family_counts"], {SRC_A: 2, SRC_B: 1})
        self.assertEqual(page["unmatched"], [])
        self.assertEqual(page["component_total"], 3)
        by_family = {group["family"]: group for group in page["groups"]}
        self.assertEqual([m["label"] for m in by_family[SRC_A]["members"]], ["gear_a", "gear_b"])
        self.assertEqual(by_family[SRC_B]["count"], 1)
        self.assertTrue(page["appearance_baseline"]["present"])

    def test_explicit_family_merging_across_sources(self):
        self.write_model()
        page = appearance.preview_recolor(
            self.model_id, 3, families={"drive": ["gear_a", "gear_b", "shaft_main"]}
        )
        self.assertEqual(page["mode"], "explicit")
        self.assertEqual(page["family_counts"], {"drive": 3})
        (group,) = page["groups"]
        self.assertEqual(group["family"], "drive")
        self.assertEqual(
            {member["matched_by"] for member in group["members"]},
            {"gear_a", "gear_b", "shaft_main"},
        )
        self.assertEqual(page["unmatched"], [])

    def test_multi_label_same_source_still_groups(self):
        # One component carries two labels but every binding names SRC_A, so
        # its source is unique and automatic grouping is determinate.
        aliases = standard_aliases()
        aliases["gear_x"] = alias("gear_x", SRC_A, 40)
        self.write_model(aliases=aliases)
        page = appearance.preview_recolor(self.model_id, 3)
        self.assertEqual(page["family_counts"], {SRC_A: 2, SRC_B: 1})
        by_feature = {
            member["feature_id"]: member for group in page["groups"] for member in group["members"]
        }
        self.assertEqual(by_feature[40]["label"], "gear_a")
        self.assertEqual(by_feature[40]["matched_by"], "gear_a")
        self.assertEqual(by_feature[40]["source_model_id"], SRC_A)

    def test_source_conflicts_refuse_automatic_grouping(self):
        # Same component, two labels with different sources: indeterminate.
        aliases = standard_aliases()
        aliases["gear_x"] = alias("gear_x", SRC_B, 40)
        self.write_model(aliases=aliases)
        with self.assertRaises(ValueError) as caught:
            appearance.preview_recolor(self.model_id, 3)
        self.assertIn("missing or conflicting sources", str(caught.exception))
        self.assertIn("explicit families table", str(caught.exception))
        # The explicit table is the documented escape hatch: feature IDs select
        # the conflicted components without guessing a source.
        page = appearance.preview_recolor(
            self.model_id, 3, families={"mixed": [40, "gear_b", "shaft_main"]}
        )
        self.assertEqual(page["family_counts"], {"mixed": 3})

    def test_unlabeled_component_refuses_automatic_grouping(self):
        records = standard_records() + [component(43, "c_job_3")]
        self.write_model(records=records)
        with self.assertRaises(ValueError) as caught:
            appearance.preview_recolor(self.model_id, 3)
        self.assertIn("missing or conflicting sources", str(caught.exception))

    def test_explicit_table_refuses_duplicate_components(self):
        self.write_model()
        with self.assertRaises(ValueError) as caught:
            appearance.preview_recolor(
                self.model_id,
                3,
                families={"one": ["gear_a", "gear_b"], "two": ["gear_b", "shaft_main"]},
            )
        self.assertIn("duplicated components are refused", str(caught.exception))
        self.assertIn("41", str(caught.exception))

    def test_explicit_table_refuses_omitted_components(self):
        self.write_model()
        with self.assertRaises(ValueError) as caught:
            appearance.preview_recolor(self.model_id, 3, families={"only": ["gear_a"]})
        self.assertIn("omits 2 component(s)", str(caught.exception))
        self.assertIn("cover every checkpoint component exactly once", str(caught.exception))

    def test_unmatched_entries_are_reported_not_invented(self):
        self.write_model()
        families = {**DRIVE_FAMILIES, "ghost_family": ["nope_component"]}
        palette = {**DRIVE_PALETTE, "ghost_family": [0.1, 0.1, 0.1]}
        page = appearance.preview_recolor(self.model_id, 3, palette=palette, families=families)
        self.assertEqual(page["unmatched"], [{"family": "ghost_family", "ref": "nope_component"}])
        self.assertEqual(page["unmatched_count"], 1)
        self.assertEqual(page["family_counts"]["ghost_family"], 0)

    def test_duplicated_checkpoint_component_ids_refused(self):
        records = standard_records() + [component(40, "c_job_dup")]
        self.write_model(records=records)
        with self.assertRaises(ValueError) as caught:
            appearance.preview_recolor(self.model_id, 3)
        self.assertIn("duplicated component feature_ids", str(caught.exception))

    def test_invalid_rgb_including_booleans_refused(self):
        self.write_model()
        bad = [
            [0.5, True, 0.2],
            [True, 0, 0],
            [0.5, False, 0.2],
            [0.5, 0.2],
            [0.5, 0.2, 0.1, 0.0],
            [0.5, 0.2, 1.5],
            [0.5, -0.1, 0.2],
            [0.5, float("nan"), 0.2],
            [0.5, float("inf"), 0.2],
            ["0.5", 0.2, 0.1],
            [0.5, None, 0.1],
            [0.5, "True", 0.1],
            "not-a-color",
        ]
        for color in bad:
            with self.subTest(color=color):
                with self.assertRaises(ValueError):
                    appearance.preview_recolor(
                        self.model_id,
                        3,
                        palette={"fam": color},
                        families={"fam": ["gear_a", "gear_b", "shaft_main"]},
                    )
        with self.assertRaises(ValueError):
            appearance.submit_recolor(
                self.model_id,
                3,
                palette={"fam": [0.5, True, 0.2]},
                families={"fam": ["gear_a", "gear_b", "shaft_main"]},
            )

    def test_stale_revision_refused(self):
        self.write_model()
        with self.assertRaises(ValueError) as caught:
            appearance.preview_recolor(self.model_id, 2)
        self.assertIn("Stale revision", str(caught.exception))
        with self.assertRaises(ValueError) as caught:
            appearance.submit_recolor(
                self.model_id, 99, palette=DRIVE_PALETTE, families=DRIVE_FAMILIES
            )
        self.assertIn("Stale revision", str(caught.exception))

    def test_non_assembly_refused(self):
        self.write_model(model_type="part", name="wb_part", records=[], aliases={})
        with self.assertRaises(ValueError) as caught:
            appearance.preview_recolor(self.model_id, 3)
        self.assertIn("single-level assemblies only", str(caught.exception))
        with self.assertRaises(ValueError) as caught:
            appearance.submit_recolor(
                self.model_id, 3, palette=DRIVE_PALETTE, families=DRIVE_FAMILIES
            )
        self.assertIn("Assembly operations require an MCP assembly model", str(caught.exception))

    def test_missing_components_and_checkpoint_refused(self):
        self.write_model(records=[], aliases={})
        with self.assertRaises(ValueError) as caught:
            appearance.preview_recolor(self.model_id, 3)
        self.assertIn("lists no assembly components", str(caught.exception))
        self.write_model(with_part=False)
        with self.assertRaises(ValueError) as caught:
            appearance.preview_recolor(self.model_id, 3)
        self.assertIn("No verified saved checkpoint", str(caught.exception))
        self.write_model(pending_job="b" * 32)
        with self.assertRaises(ValueError) as caught:
            appearance.preview_recolor(self.model_id, 3)
        self.assertIn("not usable while a job is pending", str(caught.exception))
        self.write_model(status="unknown_outcome")
        with self.assertRaises(ValueError) as caught:
            appearance.preview_recolor(self.model_id, 3)
        self.assertIn("not 'ready'", str(caught.exception))


class PreviewProtocol(AppearanceFixture):
    """Plan acceptance: 预览与协议."""

    def test_preview_touches_no_toolkit_no_job_and_keeps_revision(self):
        self.write_model()
        with ExitStack() as stack:
            lock = stack.enter_context(
                patch.object(
                    bridge,
                    "toolkit_lock",
                    side_effect=AssertionError("toolkit_lock must not be taken"),
                )
            )
            popen = stack.enter_context(
                patch("subprocess.Popen", side_effect=AssertionError("no process may start"))
            )
            build = stack.enter_context(
                patch.object(bridge, "build_native", side_effect=AssertionError("no native build"))
            )
            page = appearance.preview_recolor(self.model_id, 3)
        self.assertEqual((lock.call_count, popen.call_count, build.call_count), (0, 0, 0))
        self.assertEqual(page["families_total"], 2)
        self.assertTrue(page["dry_run"])
        self.assertFalse(any((self.directory / "jobs").iterdir()))
        model = self.read_model()
        self.assertEqual(model["revision"], 3)
        self.assertNotIn("pending_job", model)

    def test_preview_pages_fit_budget_and_cursor_walks(self):
        records = [component(100 + i, f"c_job_{i}") for i in range(40)]
        aliases = {f"part_{i:02d}": alias(f"part_{i:02d}", SRC_A, 100 + i) for i in range(40)}
        self.write_model(records=records, aliases=aliases)
        families = {f"fam_{i:02d}": [f"part_{i:02d}"] for i in range(40)}
        returned = []
        cursor = None
        pages = 0
        while True:
            page = appearance.preview_recolor(
                self.model_id, 3, families=families, limit=7, cursor=cursor
            )
            pages += 1
            self.assertLessEqual(serialized_size(page), RESPONSE_BUDGET)
            self.assertLessEqual(page["returned_count"], 7)
            self.assertEqual(len(page["family_counts"]), 40)
            returned.extend(group["family"] for group in page["groups"])
            cursor = page["next_cursor"]
            if cursor is None:
                self.assertTrue(page["complete"])
                break
            self.assertLess(pages, 20)
        self.assertEqual(pages, 6)
        self.assertEqual(returned, [f"fam_{i:02d}" for i in range(40)])

    def test_single_family_over_budget_refused(self):
        records = [component(1000 + i, f"c_big_{i}") for i in range(500)]
        aliases = {f"m{i:04d}": alias(f"m{i:04d}", SRC_A, 1000 + i) for i in range(500)}
        self.write_model(records=records, aliases=aliases)
        families = {"big": [f"m{i:04d}" for i in range(500)]}
        with self.assertRaises(ValueError) as caught:
            appearance.preview_recolor(self.model_id, 3, families=families, limit=50)
        self.assertIn("32 KiB preview page budget", str(caught.exception))

    def test_cursor_invalidated_by_registry_request_and_revision_changes(self):
        self.write_model()
        first = appearance.preview_recolor(self.model_id, 3, limit=1)
        cursor = first["next_cursor"]
        self.assertIsNotNone(cursor)
        # Registry change: a new bound component joins (grouping stays valid).
        records = standard_records() + [component(43, "c_job_3")]
        aliases = standard_aliases()
        aliases["gear_c"] = alias("gear_c", SRC_C, 43)
        self.write_model(records=records, aliases=aliases)
        with self.assertRaises(ValueError) as caught:
            appearance.preview_recolor(self.model_id, 3, cursor=cursor)
        self.assertIn("Preview state changed", str(caught.exception))
        # Request change against the original state.
        self.write_model()
        with self.assertRaises(ValueError) as caught:
            appearance.preview_recolor(
                self.model_id,
                3,
                families={"solo": ["gear_a", "gear_b", "shaft_main"]},
                cursor=cursor,
            )
        self.assertIn("Preview state changed", str(caught.exception))
        # Revision change: old cursors never resume, under either revision.
        self.write_model(revision=4)
        with self.assertRaises(ValueError) as caught:
            appearance.preview_recolor(self.model_id, 3, cursor=cursor)
        self.assertIn("Stale revision", str(caught.exception))
        with self.assertRaises(ValueError) as caught:
            appearance.preview_recolor(self.model_id, 4, cursor=cursor)
        self.assertIn("Preview state changed", str(caught.exception))
        # Tampered offsets and kinds never resume a page.
        self.write_model()
        first = appearance.preview_recolor(self.model_id, 3, limit=1)
        tampered = decode_cursor(first["next_cursor"])
        tampered["offset"] = 99
        with self.assertRaises(ValueError):
            appearance.preview_recolor(
                self.model_id, 3, limit=1, cursor=appearance.encode_cursor(tampered)
            )
        tampered = decode_cursor(first["next_cursor"])
        tampered["kind"] = "session_assembly"
        with self.assertRaises(ValueError) as caught:
            appearance.preview_recolor(
                self.model_id, 3, limit=1, cursor=appearance.encode_cursor(tampered)
            )
        self.assertIn("Preview state changed", str(caught.exception))


class ExecutionAdmission(AppearanceFixture):
    """Write admission: complete palette, appearance baseline, job payload."""

    def test_execute_requires_complete_palette(self):
        self.write_model()
        with self.assertRaises(ValueError) as caught:
            appearance.submit_recolor(
                self.model_id,
                3,
                palette={"gear_family": DRIVE_PALETTE["gear_family"]},
                families=DRIVE_FAMILIES,
            )
        self.assertIn("missing colors for: ['shaft_family']", str(caught.exception))
        with self.assertRaises(ValueError) as caught:
            appearance.submit_recolor(
                self.model_id,
                3,
                palette={**DRIVE_PALETTE, "ghost": [0, 0, 0]},
                families=DRIVE_FAMILIES,
            )
        self.assertIn("does not name a family", str(caught.exception))
        with self.assertRaises(ValueError) as caught:
            appearance.submit_recolor(self.model_id, 3, palette=None, families=DRIVE_FAMILIES)
        self.assertIn("requires a palette", str(caught.exception))
        with self.assertRaises(ValueError) as caught:
            appearance.submit_recolor(
                self.model_id,
                3,
                palette={"f" * 32: [1, 0, 0]},
                families=None,
            )
        self.assertIn("palette keys do not name any family", str(caught.exception))

    def test_execute_refuses_preview_parameters(self):
        self.write_model()
        with self.assertRaises(ValueError) as caught:
            appearance.submit_recolor(self.model_id, 3, cursor="abc")
        self.assertIn("cursor is only for dry_run previews", str(caught.exception))
        with self.assertRaises(ValueError) as caught:
            appearance.submit_recolor(self.model_id, 3, limit=10)
        self.assertIn("limit is only for dry_run previews", str(caught.exception))

    def test_checkpoint_without_appearance_baseline_refused_on_write(self):
        self.write_model(records=standard_records(with_appearance=False))
        with self.assertRaises(ValueError) as caught:
            appearance.submit_recolor(
                self.model_id, 3, palette=DRIVE_PALETTE, families=DRIVE_FAMILIES
            )
        self.assertIn("predates component appearance baselines", str(caught.exception))
        self.assertIn("creo_save_model", str(caught.exception))
        with self.assertRaises(ValueError) as caught:
            appearance.prepare_recolor_operations(
                self.read_model(),
                [{"op": "recolor_assembly", "palette": DRIVE_PALETTE, "families": DRIVE_FAMILIES}],
            )
        self.assertIn("creo_save_model", str(caught.exception))
        # The preview still reports grouping and flags the missing baseline
        # instead of silently pretending execution would succeed.
        page = appearance.preview_recolor(self.model_id, 3)
        self.assertFalse(page["appearance_baseline"]["present"])
        self.assertEqual(page["appearance_baseline"]["missing_count"], 3)
        self.assertIn("creo_save_model", page["appearance_baseline"]["note"])

    def test_prepare_builds_native_contract_payload(self):
        model = self.write_model()
        operations = [
            {
                "op": "recolor_assembly",
                "palette": DRIVE_PALETTE,
                "families": {"gear_family": ["gear_a", "gear_b"], "shaft_family": [42]},
            }
        ]
        (op,) = appearance.prepare_recolor_operations(model, operations)
        self.assertEqual(set(op), {"op", "assignments", "families"})
        self.assertEqual(op["op"], "recolor_assembly")
        self.assertEqual(op["families"], ["gear_family", "shaft_family"])
        self.assertEqual(len(op["assignments"]), 3)
        by_ref = {entry["label"]: entry for entry in op["assignments"]}
        self.assertEqual(
            by_ref["gear_a"],
            {
                "label": "gear_a",
                "family": "gear_family",
                "rgb": [0.9, 0.6, 0.1],
                "feature_id": 40,
            },
        )
        self.assertEqual(by_ref["gear_b"]["feature_id"], 41)
        self.assertEqual(
            by_ref[42],
            {
                "label": 42,
                "family": "shaft_family",
                "rgb": [0.2, 0.4, 0.8],
                "feature_id": 42,
            },
        )

    def test_prepare_ignores_unmatched_entries_in_assignments(self):
        model = self.write_model()
        operations = [
            {
                "op": "recolor_assembly",
                "palette": {**DRIVE_PALETTE, "ghost_family": [0, 0, 0]},
                "families": {**DRIVE_FAMILIES, "ghost_family": ["nope_component"]},
            }
        ]
        (op,) = appearance.prepare_recolor_operations(model, operations)
        self.assertEqual(op["families"], ["gear_family", "shaft_family", "ghost_family"])
        self.assertEqual(
            {entry["label"] for entry in op["assignments"]}, {"gear_a", "gear_b", "shaft_main"}
        )
        self.assertEqual(len(op["assignments"]), 3)

    def test_execute_submits_job_with_resolved_payload(self):
        self.write_model()
        self.write_template_config()
        captured = {}

        def fake_popen(*args, **kwargs):
            captured["args"] = args
            return None

        with patch.object(general.subprocess, "Popen", side_effect=fake_popen):
            manifest = appearance.submit_recolor(
                self.model_id,
                3,
                palette={SRC_A: [1, 0, 0], SRC_B: [0, 0, 1]},
                families=None,
            )
        self.assertIn("job_id", manifest)
        self.assertEqual(manifest["model_id"], self.model_id)
        request = bridge.read_json(bridge.job_path(manifest["job_id"]) / "request.json")
        op = request["operations"][0]
        self.assertEqual(set(op), {"op", "assignments", "families"})
        self.assertEqual(op["families"], [SRC_A, SRC_B])
        self.assertEqual(
            {entry["label"] for entry in op["assignments"]}, {"gear_a", "gear_b", "shaft_main"}
        )
        for entry in op["assignments"]:
            self.assertEqual(set(entry), {"label", "family", "rgb", "feature_id"})
        self.assertEqual(captured["args"][0][2], "run-job")
        model = self.read_model()
        self.assertEqual(model["revision"], 3)
        self.assertEqual(model["pending_job"], manifest["job_id"])


class PlanOperationContract(AppearanceFixture):
    """recolor_assembly as a creo_execute_plan operation."""

    def test_plan_operation_refuses_plan_created_components(self):
        plan = [
            {"op": "assemble_component", "label": "gear_a", "source_model_id": "b" * 32},
            {
                "op": "recolor_assembly",
                "palette": {"fam": [1, 0, 0]},
                "families": {"fam": ["gear_a"]},
            },
        ]
        with self.assertRaises(ValueError) as caught:
            validate_operations(plan)
        self.assertIn("created by assemble_component", str(caught.exception))
        plan.reverse()
        with self.assertRaises(ValueError):
            validate_operations(plan)

    def test_plan_operation_refuses_preview_parameters(self):
        for extra in ({"dry_run": True}, {"limit": 10}, {"cursor": "abc"}):
            with self.subTest(extra=extra):
                with self.assertRaises(ValueError):
                    validate_operations(
                        [
                            {
                                "op": "recolor_assembly",
                                "palette": {"fam": [1, 0, 0]},
                                "families": {"fam": ["gear_a"]},
                                **extra,
                            }
                        ]
                    )

    def test_plan_operation_shape_normalization(self):
        (op,) = validate_operations(
            [
                {
                    "op": "recolor_assembly",
                    "palette": {"fam": [1, 0, 0.5]},
                    "families": {"fam": ["42", "gear_a"]},
                }
            ]
        )
        self.assertEqual(op["palette"], {"fam": [1.0, 0.0, 0.5]})
        self.assertEqual(op["families"], {"fam": [42, "gear_a"]})
        with self.assertRaises(ValueError):
            validate_operations([{"op": "recolor_assembly", "palette": {"fam": [1, True, 0]}}])
        with self.assertRaises(ValueError):
            validate_operations(
                [
                    {
                        "op": "recolor_assembly",
                        "palette": {"fam": [1, 0, 0]},
                        "families": {"Bad": ["gear_a"]},
                    }
                ]
            )

    def test_prepare_refuses_plan_created_labels_at_admission(self):
        model = self.write_model()
        operations = [
            {"op": "assemble_component", "label": "new_gear", "source_model_id": "b" * 32},
            {
                "op": "recolor_assembly",
                "palette": {**DRIVE_PALETTE, "later": [0, 0, 0]},
                "families": {**DRIVE_FAMILIES, "later": ["new_gear"]},
            },
        ]
        with self.assertRaises(ValueError) as caught:
            appearance.prepare_recolor_operations(model, operations)
        self.assertIn("already exist before the plan runs", str(caught.exception))
        self.assertIn("new_gear", str(caught.exception))


class ResultProjection(unittest.TestCase):
    """Job result projection: full recolor block and compact summary."""

    def test_recolor_block_keeps_unknown_fields_unknown(self):
        block = appearance.project_recolor(
            {
                "painted": 2,
                "readback_before_save": [
                    {"label": "gear_a", "family": "fam", "rgb_read": [1, 0, 0], "abs_err": 1e-9}
                ],
                "readback_after_reload": "broken",
                "component_appearance_baseline": [
                    {"label": "gear_a", "appearance": {"state": "absent"}},
                    {"label": 42, "appearance": {"state": "bogus", "rgb": [0, 0, 0, 0]}},
                ],
            }
        )
        self.assertEqual(block["painted"], 2)
        self.assertIsNone(block["unmatched"])
        self.assertIsNone(block["family_counts"])
        self.assertIsNone(block["readback_tolerance"])
        self.assertIsNone(block["readback_all_within_tolerance"])
        self.assertIsNone(block["readback_after_reload"])
        entry = block["readback_before_save"][0]
        self.assertEqual(entry["rgb_read"], [1.0, 0.0, 0.0])
        self.assertEqual(entry["abs_err"], 1e-9)
        self.assertIsNone(entry["rgb_requested"])
        self.assertIsNone(entry["query_code"])
        first, second = block["component_appearance_baseline"]
        self.assertEqual(first["appearance"], {"state": "absent", "rgb": None, "query_code": None})
        self.assertEqual(second["label"], 42)
        self.assertIsNone(second["appearance"]["state"])
        self.assertIsNone(second["appearance"]["rgb"])

    def test_rollback_verification_passthrough(self):
        rows = [
            {
                "label": "gear_a",
                "baseline_state": "present",
                "restored_state": "present",
                "abs_err": 0.0,
                "within_tolerance": True,
                "verified": True,
            }
        ]
        block = appearance.project_recolor(
            {
                "painted": 1,
                "rollback_appearance_verified": True,
                "rollback_appearance_check": rows,
            }
        )
        self.assertTrue(block["rollback_appearance_verified"])
        self.assertEqual(block["rollback_appearance_check"], rows)
        annotated = {"recolor": {"painted": 1, "rollback_appearance_verified": True}}
        appearance.annotate_recolor(annotated)
        self.assertTrue(annotated["recolor"]["rollback_appearance_verified"])
        self.assertIsNone(annotated["recolor"]["rollback_appearance_check"])

    def test_rollback_verification_never_fabricated(self):
        block = appearance.project_recolor({"painted": 1})
        self.assertIsNone(block["rollback_appearance_verified"])
        self.assertIsNone(block["rollback_appearance_check"])
        broken = appearance.project_recolor(
            {"rollback_appearance_verified": "yes", "rollback_appearance_check": "rows"}
        )
        self.assertIsNone(broken["rollback_appearance_verified"])
        self.assertIsNone(broken["rollback_appearance_check"])

    def test_missing_or_broken_block_is_never_fabricated(self):
        self.assertIsNone(appearance.project_recolor(None)["painted"])
        self.assertIsNone(appearance.project_recolor("junk")["family_counts"])
        result = {"success": True}
        appearance.annotate_recolor(result)
        self.assertNotIn("recolor", result)
        annotated = {"recolor": {"painted": -1, "readback_tolerance": "x"}}
        appearance.annotate_recolor(annotated)
        self.assertIsNone(annotated["recolor"]["painted"])
        self.assertIsNone(annotated["recolor"]["readback_tolerance"])

    def test_compact_recolor_keeps_counts_and_verification_only(self):
        full = appearance.project_recolor(
            {
                "painted": 3,
                "unmatched": [{"family": "ghost", "ref": "nope"}],
                "family_counts": {"fam": 3},
                "readback_before_save": [{}, {}, {}],
                "readback_after_reload": [{}, {}],
                "readback_tolerance": 1e-6,
                "readback_all_within_tolerance": True,
                "component_appearance_baseline": [{}],
                "rollback_appearance_verified": True,
                "rollback_appearance_check": [{}, {}],
            }
        )
        summary = appearance.compact_recolor(full)
        self.assertEqual(
            summary,
            {
                "painted": 3,
                "unmatched_count": 1,
                "family_counts": {"fam": 3},
                "readback_before_save_count": 3,
                "readback_after_reload_count": 2,
                "readback_tolerance": 1e-6,
                "readback_all_within_tolerance": True,
                "component_appearance_baseline_count": 1,
                "rollback_appearance_verified": True,
            },
        )
        self.assertNotIn("rollback_appearance_check", summary)
        self.assertEqual(appearance.compact_recolor(None)["painted"], None)
        self.assertIsNone(appearance.compact_recolor(None)["unmatched_count"])
        self.assertIsNone(appearance.compact_recolor({})["rollback_appearance_verified"])
        self.assertIsNone(
            appearance.compact_recolor({"rollback_appearance_verified": 1})[
                "rollback_appearance_verified"
            ]
        )


if __name__ == "__main__":
    unittest.main()
