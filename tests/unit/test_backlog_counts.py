"""Contract tests for the BACKLOG table/declaration count check (DEV-077)."""

import unittest
from pathlib import Path

from creo_mechdog.backlog_counts import summarize

BACKLOG = Path(__file__).resolve().parents[2] / "docs" / "BACKLOG.md"

SAMPLE = """# ledger

## 使用与计数

当前唯一 ID **3**（BUG **2**、FEAT **1**、DEV **0**）；历史说明不影响计数。

| 当前分类 | 唯一 ID 数 |
| --- | --- |
| 仍需修复 | 2 |
| 待规划 | 1 |

## 仍需修复

| ID / 工作卡 | 优先级 | 当前状态 |
| --- | --- | --- |
| [BUG-001](work-items/BUG-001.md) | P1 | 仍需修复 |
| [BUG-002](work-items/BUG-002.md) | P2 | 仍需修复 |

## 待规划

| ID / 工作卡 | 优先级 | 当前状态 |
| --- | --- | --- |
| [FEAT-001](work-items/FEAT-001.md) | P1 | 待规划 |
"""


class BacklogCountsTest(unittest.TestCase):
    def test_consistent_sample_has_no_problems(self):
        report = summarize(SAMPLE)
        self.assertEqual(report["actual"], {"BUG": 2, "FEAT": 1, "DEV": 0})
        self.assertEqual(report["actual_total"], 3)
        self.assertEqual(report["category_total"], 3)
        self.assertEqual(report["duplicates"], [])
        self.assertEqual(report["problems"], [])
        self.assertTrue(report["consistent"])

    def test_stale_declared_total_is_reported(self):
        report = summarize(SAMPLE.replace("**3**（BUG", "**4**（BUG", 1))
        self.assertFalse(report["consistent"])
        self.assertIn("declared_total", report["problems"])

    def test_stale_prefix_count_is_reported(self):
        report = summarize(SAMPLE.replace("FEAT **1**", "FEAT **2**", 1))
        self.assertFalse(report["consistent"])
        self.assertIn("declared_FEAT", report["problems"])

    def test_category_rows_must_sum_to_table_rows(self):
        report = summarize(SAMPLE.replace("| 待规划 | 1 |", "| 待规划 | 2 |", 1))
        self.assertFalse(report["consistent"])
        self.assertIn("category_total", report["problems"])

    def test_duplicate_id_is_reported(self):
        report = summarize(
            SAMPLE.replace(
                "[FEAT-001](work-items/FEAT-001.md)",
                "[BUG-001](work-items/BUG-001.md)",
                1,
            )
        )
        self.assertFalse(report["consistent"])
        self.assertEqual(report["duplicates"], ["BUG-001"])

    def test_current_repository_backlog_is_consistent(self):
        report = summarize(BACKLOG.read_text(encoding="utf-8"))
        self.assertTrue(report["consistent"], report["problems"])


if __name__ == "__main__":
    unittest.main()
