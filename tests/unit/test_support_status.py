"""FEAT-045: support_status.assembly_checks must match the shipped read-only tool."""

import unittest

import capabilities
import server


class SupportStatusAssemblyChecks(unittest.TestCase):
    def test_assembly_checks_match_the_shipped_read_only_tool(self):
        entry = server._support_status()["assembly_checks"]
        self.assertEqual(entry["status"], "supported_limited")
        self.assertEqual(entry["tool"], "creo_inspect_session_assembly")
        self.assertEqual(entry["tool"], capabilities.families()["session_assembly"]["tool"])

    def test_summary_states_read_only_scope_and_restricted_scenarios(self):
        summary = server._support_status()["assembly_checks"]["summary"]
        self.assertIn("read-only", summary)
        for scenario in ("nested", "repeated instances", "suppressed", "missing"):
            self.assertIn(scenario, summary)
        self.assertIn("not live-triggered", summary)

    def test_summary_keeps_adoption_and_write_paths_refused(self):
        summary = server._support_status()["assembly_checks"]["summary"]
        self.assertIn("No write path", summary)
        self.assertIn("adoption/reconcile stays refused", summary)
        self.assertNotIn("not available yet", summary)
