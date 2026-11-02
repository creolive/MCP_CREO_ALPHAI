"""BUG-106: both session dead ends must name the next call, not just the refusal.

The 0.11.0/0.11.1 feedback hit two bare refusals that left manual registry
edits as the only way out:

- ``creo_save_model``: "Loaded model origin does not match this MCP model's
  output directory" — no hint that a same-name session copy has to be erased;
- ``creo_erase_session_models``: "The model has unsaved changes; save or
  discard them in Creo first" — no hint that inspect+apply must be re-run after
  the GUI save.

The guidance is a copy change only: no automatic erase, no adoption, no change
to the refusal conditions themselves.
"""

import unittest
from pathlib import Path

SOURCE = (Path(__file__).resolve().parents[2] / "native/generic.cpp").read_text(encoding="utf-8")


def window(anchor, span=900):
    position = SOURCE.index(anchor)
    return SOURCE[position : position + span]


class SaveOriginGuidanceTests(unittest.TestCase):
    anchor = "Loaded model origin does not match this MCP model's output directory"

    def test_refusal_names_the_erase_call_and_the_retry(self):
        text = window(self.anchor)
        self.assertIn("creo_erase_session_models(targets=[", text)
        self.assertIn("name", text)
        self.assertIn("model_type", text)
        self.assertIn("retry", text.lower())

    def test_refusal_never_offers_a_silent_erase_or_adoption(self):
        text = window(self.anchor)
        self.assertNotIn("adopt_session_copy", text)
        self.assertNotIn("automatically", text.replace("is never erased automatically", ""))
        self.assertNotIn("will be erased", text)


class EraseModifiedGuidanceTests(unittest.TestCase):
    anchor = "The model has unsaved changes"

    def test_refusal_names_the_save_inspect_apply_chain(self):
        text = window(self.anchor)
        self.assertIn("Creo", text)
        self.assertIn("creo_erase_session_models(action='inspect')", text)
        self.assertIn("apply", text)

    def test_refusal_never_claims_to_save_or_discard_for_the_user(self):
        text = window(self.anchor)
        self.assertNotIn("we will save", text)
        self.assertIn("does not", text)


class NoAdoptionPathTests(unittest.TestCase):
    def test_adoption_stays_unimplemented(self):
        self.assertNotIn("adopt_session_copy", SOURCE)


if __name__ == "__main__":
    unittest.main()
