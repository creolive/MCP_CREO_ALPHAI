"""Contract tests for bounded native.log stage attribution (BUG-109)."""

import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path

from creo_mechdog.native_stage import stall_report

BASE_MS = 1_700_000_000_000


def at(seconds: float) -> datetime:
    return datetime.fromtimestamp(BASE_MS / 1000 + seconds, tz=timezone.utc)


class NativeStageReport(unittest.TestCase):
    def setUp(self):
        self.directory = Path(self.enterContext(tempfile.TemporaryDirectory()))

    def write(self, text, *, encoding="utf-8"):
        (self.directory / "native.log").write_bytes(text.encode(encoding))

    def test_missing_log_is_explicitly_unreadable(self):
        report = stall_report(self.directory, now=at(0))
        self.assertFalse(report["readable"])
        self.assertEqual(report["reason"], "native_log_missing")
        self.assertIsNone(report["stage"])
        self.assertIsNone(report["sub_stage"])
        self.assertIsNone(report["log_bytes"])

    def test_last_phase_and_substage_are_reported(self):
        self.write(
            "PHASE=execute_sketch\n"
            "PHASE=verify_model\n"
            f"STAGE name=verify_model_regenerate elapsed_ms=1200 since_start_ms=1200 ts={BASE_MS}\n"
            f"STAGE name=verify_model_inspect elapsed_ms=800 since_start_ms=2000 ts={BASE_MS + 5000}\n"
        )
        report = stall_report(self.directory, now=at(10.5))
        self.assertTrue(report["readable"])
        self.assertEqual(report["stage"], "verify_model")
        self.assertEqual(report["sub_stage"], "verify_model_inspect")
        self.assertEqual(report["elapsed_ms"], 800)
        self.assertEqual(report["since_start_ms"], 2000)
        self.assertEqual(report["stages_seen"], 2)
        self.assertAlmostEqual(report["idle_seconds"], 5.5, places=3)
        self.assertIsNone(report["reason"])

    def test_phase_only_log_keeps_stage_and_says_why_timing_is_missing(self):
        self.write("PHASE=save_and_reload\nPHASE=verify_model\n")
        report = stall_report(self.directory, now=at(0))
        self.assertEqual(report["stage"], "verify_model")
        self.assertIsNone(report["sub_stage"])
        self.assertIsNone(report["elapsed_ms"])
        self.assertIsNone(report["idle_seconds"])
        self.assertEqual(report["reason"], "no_stage_timing")

    def test_malformed_timing_degrades_without_raising(self):
        self.write(
            "PHASE=verify_model\n"
            "STAGE name=verify_model_save elapsed_ms=abc since_start_ms=?? ts=zzz\n"
        )
        report = stall_report(self.directory, now=at(0))
        self.assertEqual(report["sub_stage"], "verify_model_save")
        self.assertIsNone(report["elapsed_ms"])
        self.assertIsNone(report["since_start_ms"])
        self.assertIsNone(report["idle_seconds"])

    def test_tail_is_bounded_but_total_bytes_stay_visible(self):
        filler = "noise line without stage markers\n" * 500
        self.write(
            filler
            + "PHASE=verify_model\n"
            + f"STAGE name=verify_model_reload elapsed_ms=40 since_start_ms=90 ts={BASE_MS}\n"
        )
        report = stall_report(self.directory, now=at(2))
        self.assertEqual(report["log_bytes"], len((self.directory / "native.log").read_bytes()))
        self.assertTrue(report["truncated"])
        self.assertEqual(report["sub_stage"], "verify_model_reload")

    def test_partial_trailing_line_is_ignored(self):
        self.write(
            "PHASE=verify_model\n"
            f"STAGE name=verify_model_erase elapsed_ms=5 since_start_ms=10 ts={BASE_MS}\n"
            "STAGE name=verify_model_com"
        )
        report = stall_report(self.directory, now=at(1))
        self.assertEqual(report["sub_stage"], "verify_model_erase")
        self.assertEqual(report["elapsed_ms"], 5)

    def test_undecodable_bytes_do_not_break_the_report(self):
        (self.directory / "native.log").write_bytes(b"PHASE=verify_model\n\xff\xfeSTAGE name=x\n")
        report = stall_report(self.directory, now=at(0))
        self.assertTrue(report["readable"])
        self.assertEqual(report["stage"], "verify_model")


class NativeSubStageSource(unittest.TestCase):
    """The stall report is only useful if the executor keeps emitting the lines."""

    def setUp(self):
        self.source = (Path(__file__).resolve().parents[2] / "native" / "generic.cpp").read_text(
            encoding="utf-8"
        )

    def test_stage_line_keeps_its_field_contract(self):
        self.assertIn(
            'log("STAGE name=%s elapsed_ms=%lld since_start_ms=%lld ts=%lld\\n"', self.source
        )

    def test_verify_model_steps_are_named_individually(self):
        for name in (
            "verify_model_regenerate",
            "verify_model_inspect",
            "verify_model_assertions",
            "verify_model_before_save",
            "verify_model_save",
            "verify_model_erase",
            "verify_model_reload",
            "verify_model_reload_regenerate",
            "verify_model_compare",
            "verify_model_after_reload",
            "verify_model_preview",
        ):
            self.assertIn(f'generic_substage("{name}")', self.source, name)

    def test_receipts_carry_the_completed_sub_stages(self):
        self.assertIn('report["verify_stages"] = verify_stages;', self.source)

    def test_phase_lines_are_not_removed(self):
        self.assertIn('log("PHASE=%s\\n", phase.c_str());', self.source)

    def test_connect_is_bracketed_by_timed_substages(self):
        # R12/BUG-109: connect time has to be attributable on its own, so a slow
        # session attach is not folded into the first operation stage.
        connect = self.source.index("CK(connect_creo(&process));")
        before = self.source.rfind('generic_substage("connect");', 0, connect)
        after = self.source.find('generic_substage("connected");', connect)
        self.assertGreater(before, 0)
        self.assertGreater(after, connect)


if __name__ == "__main__":
    unittest.main()
