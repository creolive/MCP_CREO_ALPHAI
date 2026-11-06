"""BUG-111 follow-up: the transform selection evidence must use real counts, and
the retired "four copies per batch" advice must stay retired.

Two defects were found after the 0.11.7 delivery:

1. ``native/placement.cpp`` read the model counts from ``state["counts"]``, an
   object ``inspection()`` never publishes. The live inspection publishes the
   counts as the ``features`` / ``surfaces`` / ``bodies`` arrays (plus
   ``body_counts`` for the body split), so every count fell back to -1 and the
   evidence reported "unknown" for data that was right there.
2. The outward-facing wording (tool description, capability limits, syntax
   reference) still told callers to copy at most four times per batch and
   re-reference the current body. C6 proved that workaround does not work, so
   the advice was withdrawn in the same release; the public texts have to match
   that conclusion.
"""

import unittest
from pathlib import Path

from creo_mechdog.capabilities import families

ROOT = Path(__file__).resolve().parents[2]
NATIVE = ROOT / "native"

RETIRED_ADVICE = (
    "copy at most four times per batch",
    "copies the same body more than four times in one batch",
    "split large copy sets and re-reference the current body IDs",
    "请拆成 ≤4 个/批",
)


class NativeSelectionCounts(unittest.TestCase):
    """The counts must come from the fields the inspection really publishes."""

    def setUp(self):
        self.placement = (NATIVE / "placement.cpp").read_text(encoding="utf-8")

    def test_counts_are_read_from_the_inspection_arrays(self):
        for field in ("features", "surfaces", "bodies"):
            self.assertIn(f'inspection_count(state, "{field}")', self.placement)

    def test_the_never_published_counts_object_is_gone(self):
        self.assertNotIn('state["counts"]', self.placement)

    def test_a_count_the_inspection_lacks_stays_explicitly_unknown(self):
        # null in the published JSON, -1 only in the log line: a missing count
        # must not be dressed up as a number, and an available one must not be
        # published as unknown.
        self.assertIn("feature_count < 0 ? J(nullptr) : J(feature_count)", self.placement)
        self.assertIn("surface_count < 0 ? J(nullptr) : J(surface_count)", self.placement)
        self.assertIn("body_count < 0 ? J(nullptr) : J(body_count)", self.placement)
        self.assertIn("active_body_count < 0 ? J(nullptr) : J(active_body_count)", self.placement)

    def test_the_active_body_split_is_read_from_body_counts(self):
        self.assertIn('state["body_counts"]', self.placement)
        self.assertIn('counts.contains("active")', self.placement)


class PublicBoundaryWording(unittest.TestCase):
    """The published texts must state the current conclusion, not the old one."""

    def setUp(self):
        self.server = (ROOT / "server.py").read_text(encoding="utf-8")
        self.syntax = (ROOT / "docs" / "REFERENCE_SYNTAX.md").read_text(encoding="utf-8")
        self.compatibility = (ROOT / "docs" / "COMPATIBILITY.md").read_text(encoding="utf-8")

    def test_capability_limits_withdraw_the_batch_advice(self):
        limits = families()["placement"]["limits"]
        for retired in RETIRED_ADVICE:
            self.assertNotIn(retired, limits)
        self.assertIn("withdrawn", limits)
        self.assertIn("keep_original", limits)

    def test_the_tool_description_does_not_repeat_the_retired_advice(self):
        for retired in RETIRED_ADVICE:
            self.assertNotIn(retired, self.server)
        self.assertIn("accumulate inside the same body", self.server)

    def test_the_syntax_reference_marks_the_advice_as_retired(self):
        self.assertIn("已作废", self.syntax)
        self.assertIn("单批 ≤4 个副本", self.syntax)

    def test_the_compatibility_matrix_marks_the_historical_section(self):
        self.assertIn("本段为 0.11.6 的历史结论", self.compatibility)


if __name__ == "__main__":
    unittest.main()
