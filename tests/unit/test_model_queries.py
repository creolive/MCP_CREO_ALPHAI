"""BUG-013/014 budgets, snapshot binding, unknown counts and lossless pages."""

import copy
import unittest

from creo_mechdog.model_queries import (
    RESPONSE_BUDGET,
    decode_cursor,
    encode_cursor,
    inspect_page,
    inspection_summary,
    list_page,
    model_summary,
    serialized_size,
)
from creo_mechdog.query_client import read_full_model


def model(count=3):
    return {
        "model_id": "a" * 32,
        "model_name": "test",
        "revision": 3,
        "status": "ready",
        "updated_at": "2026-10-14",
        "aliases": {"base": {"feature_id": 1}},
        "inspection": {
            "healthy": True,
            "has_solid": True,
            "volume_mm3": 123,
            "features": [
                {
                    "id": i,
                    "name": "特征" * 50,
                    "dimensions": [{"id": i, "value": 4}],
                    "geometry_items": [{"id": i, "type": 2}],
                }
                for i in range(count)
            ],
            "edges": [{"id": i} for i in range(count)],
            "surfaces": [],
            "bodies": [{"id": 1}],
            "parameters": {"SIZE": {"value": 4}},
        },
    }


class ModelQueryTests(unittest.TestCase):
    def test_unit_query_diagnostics_and_unknown_volume_are_not_replaced_in_summary(self):
        for units, code, volume in (("mm", 0, 123), ("in", 0, None), (None, -2, None)):
            with self.subTest(units=units):
                state = {"units": units, "units_query_code": code, "volume_mm3": volume}
                before = copy.deepcopy(state)
                summary = inspection_summary(state)
                self.assertEqual(summary["units"], units)
                self.assertEqual(summary["units_query_code"], code)
                self.assertEqual(summary["volume_mm3"], volume)
                self.assertEqual(state, before)

    def test_new_failed_model_does_not_claim_verified_saved_snapshot(self):
        source = model()
        source.update(status="failed", revision=0, inspection=None, part_file=None)
        page = inspect_page(source)
        self.assertEqual(page["snapshot"]["source"], "unavailable")
        self.assertFalse(page["inspection"]["inspection_available"])
        self.assertTrue(all(value is None for value in page["inspection"]["counts"].values()))

    def test_missing_and_empty_counts_are_distinct(self):
        state = inspection_summary({"features": [], "counts": {"surfaces": 5}})
        self.assertEqual(state["counts"]["features"], 0)
        self.assertEqual(state["counts"]["surfaces"], 5)
        self.assertIsNone(state["counts"]["edges"])
        self.assertFalse(inspection_summary(None)["inspection_available"])

    def test_explicit_counts_cannot_override_real_arrays(self):
        self.assertEqual(
            inspection_summary({"features": [{}], "counts": {"features": 0}})["counts"]["features"],
            1,
        )

    def test_default_summary_does_not_mutate_or_expand_geometry(self):
        source = model(500)
        before = copy.deepcopy(source)
        page = inspect_page(source)
        self.assertEqual(source, before)
        self.assertNotIn("features", page["inspection"])
        self.assertEqual(page["inspection"]["counts"]["features"], 500)
        self.assertFalse(page["snapshot"]["live_state_verified"])
        self.assertLess(serialized_size(page), RESPONSE_BUDGET)

    def test_pages_preserve_unicode_records_under_budget(self):
        source = model(150)
        cursor = None
        found = []
        while True:
            page = inspect_page(source, "full", "features", 200, cursor)
            self.assertLessEqual(serialized_size(page), RESPONSE_BUDGET)
            found.extend(page["data"]["features"])
            cursor = page["next_cursor"]
            if not cursor:
                self.assertTrue(page["complete"])
                break
        self.assertEqual([r["id"] for r in found], list(range(150)))

    def test_cursor_binds_model_snapshot_and_section(self):
        source = model(150)
        token = inspect_page(source, "full", "features", 1)["next_cursor"]
        changed = copy.deepcopy(source)
        changed["revision"] += 1
        for current, section in ((changed, "features"), (source, "edges")):
            with self.assertRaisesRegex(ValueError, "changed"):
                inspect_page(current, "full", section, 1, token)
        changed = copy.deepcopy(source)
        changed["inspection"]["features"][0]["name"] = "changed"
        with self.assertRaisesRegex(ValueError, "changed"):
            inspect_page(changed, "full", "features", 1, token)

    def test_invalid_cursor_and_arguments(self):
        for token in ("invalid!", encode_cursor({"offset": -1}), encode_cursor({"offset": True})):
            with self.assertRaises(ValueError):
                decode_cursor(token)
        with self.assertRaises(ValueError):
            inspect_page(model(), section="features")
        with self.assertRaises(ValueError):
            inspect_page(model(), "full", "nope")
        with self.assertRaises(ValueError):
            inspect_page(model(), "full", limit=201)

    def test_oversized_record_has_actionable_error(self):
        source = model()
        source["inspection"]["features"][0]["name"] = "x" * RESPONSE_BUDGET
        with self.assertRaisesRegex(ValueError, "Single features record"):
            inspect_page(source, "full", "features")

    def test_small_explicit_full_keeps_snapshot(self):
        source = model()
        page = inspect_page(source, "full")
        self.assertEqual(page["inspection"], source["inspection"])
        self.assertEqual(page["aliases"], source["aliases"])
        self.assertTrue(page["complete"])

    def test_split_small_full_snapshot_resolves_sidecar_sections(self):
        import tempfile
        from pathlib import Path
        from unittest.mock import patch

        import bridge
        from creo_mechdog import inspection_refs

        source = model()
        with tempfile.TemporaryDirectory(prefix="t05_split_full_") as tmp:
            root = Path(tmp)
            with patch.object(bridge, "ROOT", root):
                split = dict(source)
                inspection = split.pop("inspection")
                split["inspection_ref"] = inspection_refs.make_ref(
                    inspection, root / "details", "inspection", prefix="detail"
                )
                split["inspection_summary"] = inspection_summary(inspection)
                aliases = split.pop("aliases")
                split["aliases_ref"] = inspection_refs.make_ref(
                    aliases, root / "details", "aliases", prefix="detail"
                )
                page = inspect_page(split, "full")
        # A small split snapshot still takes the whole shape, but that shape
        # must resolve the sidecar payloads instead of exposing bare *_ref
        # stubs that drop aliases/inspection from full-detail reads.
        self.assertNotIn("data", page)
        self.assertEqual(page["aliases"], source["aliases"])
        self.assertEqual(page["inspection"], source["inspection"])

    def test_list_paging_and_stale_cursor(self):
        sources = [model() for _ in range(4)]
        for i, source in enumerate(sources):
            source["model_id"] = str(i) * 32
        summaries = list(map(model_summary, sources))
        loader = lambda mid: next(m for m in sources if m["model_id"] == mid)
        first = list_page(summaries, loader, limit=2)
        last = list_page(summaries, loader, limit=2, cursor=first["next_cursor"])
        self.assertEqual(len(first["models"]) + len(last["models"]), 4)
        self.assertTrue(last["complete"])
        changed = summaries[::-1]
        with self.assertRaisesRegex(ValueError, "changed"):
            list_page(changed, loader, limit=2, cursor=first["next_cursor"])
        full = list_page(summaries, loader, detail="full", limit=1)
        self.assertIn("features", full["models"][0]["inspection"])


class QueryClientTests(unittest.IsolatedAsyncioTestCase):
    async def test_large_drawing_does_not_silently_drop_drawing_sections(self):
        source = model()
        source.update(model_type="drawing")
        source["inspection"] = {
            "model_type": "drawing",
            "units": "mm",
            "sheets": [{"sheet": 1}],
            "views": [{"id": i, "name": "view" * 100} for i in range(100)],
            "notes": [],
            "tables": [{"id": 5, "cells": [["hello"]]}],
            "models": [],
            "shown_dimensions": [],
            "new_metadata": {"state": "known"},
        }

        async def call(tool, arguments):
            return inspect_page(source, arguments["detail"], cursor=arguments.get("cursor"))

        result = await read_full_model(call, source["model_id"])
        for key, value in source["inspection"].items():
            self.assertEqual(result["inspection"][key], value)

    async def test_collect_all_sections_and_reassemble_nested_features(self):
        source = model(150)

        async def call(tool, arguments):
            self.assertEqual(tool, "creo_inspect_model")
            return inspect_page(source, arguments["detail"], cursor=arguments.get("cursor"))

        result = await read_full_model(call, source["model_id"])
        self.assertEqual(result["aliases"], source["aliases"])
        self.assertEqual(result["inspection"]["parameters"], source["inspection"]["parameters"])
        for field in ("features", "edges", "surfaces", "bodies"):
            expected = copy.deepcopy(source["inspection"][field])
            if field == "features":
                for feature in expected:
                    feature["sketch_dimensions"] = []
            self.assertEqual(result["inspection"][field], expected)
