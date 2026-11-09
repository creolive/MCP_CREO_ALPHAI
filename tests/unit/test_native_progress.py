"""B3/F06: compact per-operation progress from the native log.

F06 reported 20-op plans taking minutes with almost no readable stage output.
The worker now emits one bounded PROGRESS line at the start and end of each
requested operation; this module checks the read-side projection stays honest:
missing, malformed or out-of-window lines never become invented progress.
"""

import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path

from creo_mechdog.job_projection import compact_progress
from creo_mechdog.native_stage import LOG_SOFT_LIMIT_BYTES, stall_report

BASE_MS = 1_700_000_000_000


def at(seconds: float) -> datetime:
    return datetime.fromtimestamp(BASE_MS / 1000 + seconds, tz=timezone.utc)


def progress_line(index=3, total=20, **overrides):
    fields = {
        "index": index,
        "total": total,
        "op": "extrude",
        "label": "deck_cut",
        "state": "start",
        "elapsed_ms": 1200,
        "since_start_ms": 3400,
        "ts": BASE_MS,
    }
    fields.update(overrides)
    return "PROGRESS " + " ".join(f"{key}={value}" for key, value in fields.items()) + "\n"


class NativeProgressReport(unittest.TestCase):
    def setUp(self):
        self.directory = Path(self.enterContext(tempfile.TemporaryDirectory()))

    def write(self, text):
        (self.directory / "native.log").write_bytes(text.encode("utf-8"))

    def test_progress_line_reports_index_total_label_and_elapsed(self):
        self.write("PHASE=execute_extrude\n" + progress_line())
        report = stall_report(self.directory, now=at(0))
        self.assertEqual(report["operation_index"], 3)
        self.assertEqual(report["operation_total"], 20)
        self.assertEqual(report["operation_label"], "deck_cut")
        self.assertEqual(report["operation_state"], "start")
        self.assertEqual(report["progress_elapsed_ms"], 1200)
        self.assertEqual(report["progress_text"], "3/20 extrude:deck_cut start")
        self.assertFalse(report["log_over_soft_limit"])
        # A progress line alone is not a sub-stage timing source.
        self.assertIsNone(report["sub_stage"])
        self.assertEqual(report["stages_seen"], 0)
        self.assertEqual(report["reason"], "no_stage_timing")

    def test_last_progress_line_wins_and_progress_does_not_disturb_substages(self):
        self.write(
            "PHASE=execute_extrude\n"
            + progress_line(index=3, state="start")
            + f"STAGE name=verify_model_save elapsed_ms=40 since_start_ms=900 ts={BASE_MS}\n"
            + progress_line(
                index=4, total=20, op="sketch", label="deck_top", state="done", elapsed_ms=800
            )
        )
        report = stall_report(self.directory, now=at(0))
        self.assertEqual(report["operation_index"], 4)
        self.assertEqual(report["progress_text"], "4/20 sketch:deck_top done")
        self.assertEqual(report["progress_elapsed_ms"], 800)
        self.assertEqual(report["sub_stage"], "verify_model_save")
        self.assertEqual(report["stages_seen"], 1)
        self.assertEqual(report["elapsed_ms"], 40)

    def test_malformed_progress_lines_are_ignored_without_inventing_values(self):
        for line in (
            progress_line(index=21, total=20),
            progress_line(index=0, total=20),
            progress_line(index="three", total=20),
            progress_line(state="unknown"),
            "PROGRESS index=3\n",
        ):
            with self.subTest(line=line.strip()):
                self.write("PHASE=execute_extrude\n" + line)
                report = stall_report(self.directory, now=at(0))
                self.assertIsNone(report["operation_index"])
                self.assertIsNone(report["operation_total"])
                self.assertIsNone(report["progress_text"])

    def test_operation_without_a_label_still_reports_its_index_and_total(self):
        # DimensionsOp / ParametersOp / RelationsOp have no label field; the
        # worker's explicit "-" placeholder must not make their progress vanish.
        self.write("PHASE=execute_parameters\n" + progress_line(op="parameters", label="-"))
        report = stall_report(self.directory, now=at(0))
        self.assertEqual(report["operation_index"], 3)
        self.assertEqual(report["operation_total"], 20)
        self.assertIsNone(report["operation_label"])
        self.assertEqual(report["progress_text"], "3/20 parameters start")

    def test_malformed_line_after_a_valid_one_keeps_the_last_known_progress(self):
        self.write(progress_line(index=3) + progress_line(index=99, total=20))
        report = stall_report(self.directory, now=at(0))
        self.assertEqual(report["operation_index"], 3)
        self.assertEqual(report["progress_text"], "3/20 extrude:deck_cut start")

    def test_soft_limit_boundary_is_strictly_greater_than(self):
        line = progress_line()
        prefix = "x" * (LOG_SOFT_LIMIT_BYTES - len(line.encode("utf-8")) - 1) + "\n"
        self.write(prefix + line)
        report = stall_report(self.directory, now=at(0))
        self.assertEqual(report["log_bytes"], LOG_SOFT_LIMIT_BYTES)
        self.assertFalse(report["log_over_soft_limit"])
        self.assertTrue(report["truncated"])
        self.assertEqual(report["operation_index"], 3)

    def test_log_without_progress_keeps_all_progress_fields_unset(self):
        self.write("PHASE=verify_model\n")
        report = stall_report(self.directory, now=at(0))
        self.assertIsNone(report["operation_index"])
        self.assertIsNone(report["progress_text"])
        self.assertFalse(report["log_over_soft_limit"])

    def test_large_log_marks_soft_limit_and_bounded_read_consistently(self):
        self.write("x" * (LOG_SOFT_LIMIT_BYTES + 100) + "\n" + progress_line())
        report = stall_report(self.directory, now=at(0))
        self.assertTrue(report["truncated"])
        self.assertTrue(report["log_over_soft_limit"])
        self.assertGreater(report["log_bytes"], LOG_SOFT_LIMIT_BYTES)
        self.assertEqual(report["operation_index"], 3)

    def test_progress_outside_the_tail_window_is_not_backfilled(self):
        self.write(progress_line() + "y" * 9000 + "\n")
        report = stall_report(self.directory, now=at(0))
        self.assertTrue(report["truncated"])
        self.assertIsNone(report["operation_index"])
        self.assertIsNone(report["progress_text"])


class ProgressProjection(unittest.TestCase):
    def test_compact_progress_keeps_the_per_operation_receipt(self):
        compact = compact_progress(
            {
                "readable": True,
                "stage": "execute_extrude",
                "operation_index": 3,
                "operation_total": 20,
                "operation_label": "deck_cut",
                "operation_state": "start",
                "progress_elapsed_ms": 1200,
                "progress_text": "3/20 extrude:deck_cut start",
                "log_over_soft_limit": True,
                "log_tail": "raw log text",
            }
        )
        self.assertEqual(compact["operation_index"], 3)
        self.assertEqual(compact["operation_total"], 20)
        self.assertEqual(compact["progress_text"], "3/20 extrude:deck_cut start")
        self.assertTrue(compact["log_over_soft_limit"])
        self.assertNotIn("log_tail", compact)


class NativeProgressSourceContract(unittest.TestCase):
    """The worker must emit exactly the line the read side parses."""

    @staticmethod
    def native_source():
        return (Path(__file__).resolve().parents[2] / "native" / "generic.cpp").read_text(
            encoding="utf-8"
        )

    def test_progress_emitter_publishes_index_total_and_timings(self):
        source = self.native_source()
        start = source.index("static void generic_progress(")
        end = source.index("static V vec(", start)
        body = source[start:end]
        self.assertIn("PROGRESS index=%d total=%d", body)
        self.assertIn("state=%s", body)
        self.assertIn("elapsed_ms=%lld", body)
        self.assertIn("since_start_ms=%lld", body)
        self.assertIn("ts=%lld", body)
        self.assertIn("label.empty()", body)
        self.assertIn('"-"', body)

    def test_plan_loop_emits_start_and_done_for_each_operation(self):
        source = self.native_source()
        start = source.index('for (auto op : request["operations"])')
        end = source.index('generic_stage("verify_model")', start)
        body = source[start:end]
        self.assertGreaterEqual(body.count("generic_progress("), 2)
        self.assertIn('"start"', body)
        self.assertIn('"done"', body)
        self.assertIn("operation_total", body)


if __name__ == "__main__":
    unittest.main()
