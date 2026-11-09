"""DEV-081 / F04: connect -4 receipts name an explicit retry and never clear protection."""

from __future__ import annotations

import json
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path

from creo_mechdog import session_health

NOW = datetime(2026, 11, 9, 12, 0, 0, tzinfo=timezone.utc)


class ConnectGuidanceTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory(prefix="feedback0190_connect_")
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)
        (self.root / "jobs").mkdir()
        (self.root / "build").mkdir()

    def snapshot_for(self, toolkit_code):
        directory = self.root / "jobs" / "connect_case"
        directory.mkdir(parents=True, exist_ok=True)
        manifest = {
            "job_id": "connect_case",
            "created_at": (NOW - timedelta(seconds=120)).isoformat(),
            "kind": "generic",
            "status": "failed",
            "readonly": True,
            "model_id": "model_connect_case",
            "finished_at": (NOW - timedelta(seconds=60)).isoformat(),
            "result": {
                "connected": False,
                "toolkit_code": toolkit_code,
                "worker_exit_code": 20,
            },
        }
        (directory / "job.json").write_text(json.dumps(manifest), encoding="utf-8")
        return session_health.snapshot(self.root, now=NOW, refresh=True)

    def test_connect_minus_four_step_names_startup_retry(self):
        result = self.snapshot_for(-4)
        retry = [step for step in result["next_steps"] if step.get("step") == "retry_startup"]
        self.assertEqual(len(retry), 1)
        self.assertEqual(retry[0]["tool"], "creo_startup_status")
        self.assertIn("retry=true", retry[0]["detail"])
        self.assertIn("explicit", retry[0]["detail"].lower())

    def test_non_minus_four_has_no_retry_step(self):
        for code in (-1, None):
            with self.subTest(code=code):
                result = self.snapshot_for(code)
                steps = [step.get("step") for step in result["next_steps"]]
                self.assertNotIn("retry_startup", steps)

    def test_retry_step_never_clears_protection(self):
        result = self.snapshot_for(-4)
        steps = [step.get("step") for step in result["next_steps"]]
        self.assertIn("preserve", steps)
        self.assertIs(result["read_only"], True)
        self.assertEqual(result["toolkit_connections"], 0)
        self.assertLess(steps.index("retry_startup"), steps.index("preserve"))


if __name__ == "__main__":
    unittest.main()
