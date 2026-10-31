"""Capabilities pagination contracts (FEAT-023); synthetic payloads only."""

import time
import unittest
from unittest.mock import patch

from creo_mechdog import capability_pages as pages
from creo_mechdog.model_queries import decode_cursor, encode_cursor

PAYLOAD = {
    "name": "MCP_CREO_MechDog",
    "version": "0.4.2",
    "unit": "mm",
    "support_status": {"disk_open": {"status": "supported"}},
    "operations": ["sketch", "extrude"],
    "tools": [{"name": f"tool_{index}", "description": "d" * 40} for index in range(7)],
    "families": {f"family_{index}": {"enabled": True, "tool": f"t{index}"} for index in range(5)},
    "references": {"by_tool": {"a": 1}},
    "seed_library": {"seeds": ["two_smooth"]},
    "verified_evidence": {"historical_features": {"big": "x" * 100}},
    "runtime": {"code_root": "fixture"},
}


class CapabilityPageRules(unittest.TestCase):
    def setUp(self):
        pages.reset_snapshot()

    def _response(self, **kwargs):
        return pages.capabilities_response(lambda: dict(PAYLOAD), **kwargs)

    def test_compact_summary_is_bounded_and_lists_sections(self):
        compact = self._response()
        self.assertEqual(compact["detail"], "compact")
        self.assertEqual(compact["version"], PAYLOAD["version"])
        self.assertEqual(compact["support_status"], PAYLOAD["support_status"])
        self.assertIn("pagination", compact)
        self.assertIn("families", compact)
        self.assertEqual(compact["families"]["family_0"], {"enabled": True, "tool": "t0"})
        encoded = len(str(compact).encode("utf-8"))
        self.assertLess(encoded, pages.PAGE_BYTES)

    def test_compact_rejects_section_and_cursor(self):
        for kwargs in ({"section": "overview"}, {"cursor": encode_cursor({"offset": 0})}):
            with self.assertRaisesRegex(ValueError, "detail=full"):
                self._response(**kwargs)

    def test_full_pages_cover_every_section_without_loss_or_repeat(self):
        for section in pages.SECTIONS:
            seen: list[str] = []
            cursor = None
            while True:
                page = self._response(detail="full", section=section, limit=2, cursor=cursor)
                self.assertEqual(page["section"], section)
                self.assertLessEqual(len(str(page).encode("utf-8")), pages.PAGE_BYTES)
                seen.extend(entry["key"] for entry in page["entries"])
                cursor = page.get("next_cursor")
                if cursor is None:
                    self.assertTrue(page["complete"])
                    break
            self.assertEqual(len(seen), len(set(seen)), section)
        overview = [key for key in PAYLOAD if key not in pages._SECTION_BY_KEY]
        counted = self._response(detail="full", section="overview", limit=200)
        self.assertEqual(sorted(entry["key"] for entry in counted["entries"]), sorted(overview))
        self.assertIn("support_status", {entry["key"] for entry in counted["entries"]})

    def test_compact_and_full_overview_stay_consistent(self):
        compact = self._response()
        overview = {}
        cursor = None
        while True:
            page = self._response(detail="full", section="overview", limit=200, cursor=cursor)
            overview.update({entry["key"]: entry["value"] for entry in page["entries"]})
            cursor = page.get("next_cursor")
            if cursor is None:
                break
        for key, value in overview.items():
            self.assertEqual(compact[key], value, key)

    def test_oversize_entry_is_marked_not_truncated(self):
        payload = {
            **PAYLOAD,
            "verified_evidence": {"huge": "x" * (pages.ENTRY_BUDGET + 100)},
        }
        page = pages.capabilities_response(
            lambda: payload, detail="full", section="evidence", limit=10
        )
        entry = page["entries"][0]
        self.assertEqual(entry["key"], "huge")
        self.assertTrue(entry["oversize"])
        self.assertNotIn("value", entry)

    def test_invalid_section_and_cursor_are_rejected(self):
        with self.assertRaisesRegex(ValueError, "Unknown section"):
            self._response(detail="full", section="nope")
        with self.assertRaises(ValueError):
            self._response(detail="full", section="tools", cursor="garbage")
        first = self._response(detail="full", section="tools", limit=2)
        wrong = decode_cursor(first["next_cursor"])
        wrong["kind"] = "session_models"
        with self.assertRaisesRegex(ValueError, "invalid or the snapshot changed"):
            self._response(detail="full", section="tools", limit=2, cursor=encode_cursor(wrong))

    def test_expired_or_superseded_snapshot_rejects_old_cursors(self):
        first = self._response(detail="full", section="tools", limit=2)
        cursor = first["next_cursor"]
        with patch.object(pages.time, "monotonic", return_value=time.monotonic() + 601):
            pages.capabilities_response(lambda: dict(PAYLOAD))
            with self.assertRaisesRegex(ValueError, "invalid or the snapshot changed"):
                self._response(detail="full", section="tools", limit=2, cursor=cursor)
        pages.reset_snapshot()
        altered = {**PAYLOAD, "version": "0.5.1"}
        pages.capabilities_response(lambda: altered)
        with self.assertRaisesRegex(ValueError, "invalid or the snapshot changed"):
            self._response(detail="full", section="tools", limit=2, cursor=cursor)

    def test_limit_bounds_are_enforced(self):
        for limit in (0, 201, True, "5"):
            with self.assertRaises(ValueError):
                self._response(detail="full", section="tools", limit=limit)

    def test_extrude_enum_keys_flow_through_compact_and_full(self):
        """P05/FEAT-008: renamed extrude enum keys survive compact/full pagination."""
        payload = {
            **PAYLOAD,
            "extrude_depth_types": ["blind", "through_all"],
            "extrude_directions": ["positive", "negative", "symmetric"],
            "extrude_through_all_modes": ["cut"],
        }
        compact = pages.capabilities_response(lambda: dict(payload))
        self.assertEqual(compact["extrude_depth_types"], ["blind", "through_all"])
        overview = {}
        cursor = None
        while True:
            page = pages.capabilities_response(
                lambda: dict(payload), detail="full", section="overview", limit=2,
                cursor=cursor,
            )
            overview.update({entry["key"]: entry["value"] for entry in page["entries"]})
            cursor = page.get("next_cursor")
            if cursor is None:
                break
        for key in ("extrude_depth_types", "extrude_directions", "extrude_through_all_modes"):
            self.assertEqual(compact[key], overview[key], key)


if __name__ == "__main__":
    unittest.main()
