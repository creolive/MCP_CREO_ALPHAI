"""DEV-081 / F05: compact capabilities expose surface_loft limits; gates stay closed."""

from __future__ import annotations

import unittest

import server
from creo_mechdog import capabilities
from creo_mechdog import capability_pages as pages


class CompactLoftLimitsTests(unittest.TestCase):
    def setUp(self):
        pages.reset_snapshot()

    def _payload(self):
        return server._capabilities_payload([])

    def test_compact_families_surface_loft_has_limits_note(self):
        compact = pages.capabilities_response(self._payload)
        self.assertIn("limits_note", compact["families"]["surface_loft"])
        note = compact["families"]["surface_loft"]["limits_note"]
        self.assertIn("two sections only", note)
        self.assertIn("no smooth", note)
        self.assertLessEqual(len(note), 160)

    def test_full_families_limits_unchanged(self):
        expected = capabilities.families()["surface_loft"]["limits"]
        cursor = None
        value = None
        while True:
            page = pages.capabilities_response(
                self._payload, detail="full", section="families", limit=10, cursor=cursor
            )
            for entry in page["entries"]:
                if entry["key"] == "surface_loft":
                    value = entry["value"]
            cursor = page.get("next_cursor")
            if cursor is None or value is not None:
                break
        self.assertIsNotNone(value)
        self.assertEqual(value["limits"], expected)

    def test_boundary_fill_stays_unavailable(self):
        compact = pages.capabilities_response(self._payload)
        self.assertIn("surface_boundary_fill", compact["unavailable_operations"])


if __name__ == "__main__":
    unittest.main()
