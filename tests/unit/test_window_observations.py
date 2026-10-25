"""BUG-058: describe visible, hidden, missing and unreadable windows without killing."""

import unittest
from unittest.mock import patch

from creo_mechdog import window_observations as windows


class WindowObservations(unittest.TestCase):
    def test_window_states_and_unresponsive_observations_are_separate(self):
        with patch.object(
            windows,
            "_enumerate_windows",
            return_value=[(10, True, False), (10, False, False), (11, False, True)],
        ):
            result = windows.window_observations({10, 11, 12})
        self.assertEqual(result[10]["state"], "visible")
        self.assertEqual(result[10]["top_level_count"], 2)
        self.assertEqual(result[11]["state"], "hidden_only")
        self.assertTrue(result[11]["hung_window_observed"])
        self.assertEqual(result[12]["state"], "none_observed")

    def test_access_failure_is_unknown_not_no_window(self):
        with patch.object(windows, "_enumerate_windows", side_effect=OSError("denied")):
            self.assertEqual(windows.window_observations({10})[10]["state"], "unknown")

    def test_guidance_never_infers_death_from_window_absence(self):
        snapshot = {"processes": [{"matches": True, "windows": {"state": "none_observed"}}]}
        text = windows.connection_guidance(snapshot)
        self.assertIn("does not prove", text)
        self.assertIn("does not authorize", text)
        snapshot["processes"][0]["windows"]["state"] = "visible"
        self.assertIn("Dashboard", windows.connection_guidance(snapshot))
        snapshot["processes"][0]["matches"] = False
        self.assertIn("unconfirmed", windows.connection_guidance(snapshot))

    def test_visible_hung_guidance_distinguishes_dialogs_and_bounds_ending(self):
        snapshot = {
            "processes": [
                {
                    "matches": True,
                    "windows": {"state": "visible", "visible_hung_window_observed": True},
                }
            ]
        }
        text = windows.connection_guidance(snapshot)
        self.assertIn("hung", text)
        self.assertIn("Dashboard", text)
        self.assertIn("different condition", text)
        self.assertIn("does not prove the root cause", text)
        self.assertIn("explicit operator recovery choice", text)
        self.assertIn("never performed automatically", text)
        self.assertIn("never a precondition for retry", text)
        self.assertIn("does not authorize clearing any protection", text)

    def test_hidden_hung_windows_are_reported_separately_from_visible_ones(self):
        snapshot = {
            "processes": [
                {
                    "matches": True,
                    "windows": {
                        "state": "hidden_only",
                        "hung_window_observed": True,
                        "visible_hung_window_observed": False,
                    },
                }
            ]
        }
        text = windows.connection_guidance(snapshot)
        self.assertIn("Hung hidden windows", text)
        self.assertIn("separately", text)
        self.assertIn("does not prove a dead process", text)
        self.assertIn("explicit operator recovery choice", text)

    def test_every_actionable_branch_keeps_prechecks_and_diagnostics(self):
        states = [
            {"state": "visible", "visible_hung_window_observed": True},
            {"state": "hidden_only", "hung_window_observed": True},
            {"state": "none_observed"},
            {"state": "visible"},
        ]
        for windows_state in states:
            with self.subTest(state=windows_state["state"]):
                snapshot = {"processes": [{"matches": True, "windows": windows_state}]}
                text = windows.connection_guidance(snapshot)
                self.assertIn("unsaved models", text)
                self.assertIn("unknown or pending jobs", text)
                self.assertIn("diagnostics", text)
