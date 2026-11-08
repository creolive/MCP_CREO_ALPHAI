"""FEAT-007: creo_get_job long polling (offline only).

The optional wait polls only the persisted job record. These tests inject a
fake clock/sleep so no test waits on real time, and they assert that waiting
never submits work, takes the Toolkit channel lock, mutates the job or turns
an expired wait into a completion claim.
"""

from __future__ import annotations

import asyncio
import tempfile
import unittest
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from unittest.mock import patch

import bridge

JOB_ID = "c" * 32
OTHER_JOB_ID = "d" * 32


class FakeClock:
    """Deterministic monotonic clock whose sleep advances time."""

    def __init__(self, on_sleep=None):
        self.value = 0.0
        self.sleeps = []
        self._on_sleep = on_sleep

    def __call__(self) -> float:
        return self.value

    def sleep(self, seconds: float) -> None:
        self.sleeps.append(seconds)
        self.value += seconds
        if self._on_sleep is not None:
            self._on_sleep(len(self.sleeps), self)


class JobLongPollTests(unittest.TestCase):
    def setUp(self):
        self.root = Path(self.enterContext(tempfile.TemporaryDirectory()))
        self.enterContext(patch.object(bridge, "JOBS", self.root))
        self.enterContext(
            patch.object(
                bridge,
                "config",
                return_value={
                    "native_timeout_seconds": 600,
                    "generic_timeout_seconds": 600,
                },
            )
        )

    def write_job(self, status: str, job_id: str = JOB_ID, **extra) -> Path:
        directory = bridge.job_path(job_id)
        directory.mkdir(exist_ok=True)
        manifest = {
            "job_id": job_id,
            "kind": "plate",
            "status": status,
            "created_at": bridge.now(),
            "revision": 3,
        }
        manifest.update(extra)
        path = directory / "job.json"
        bridge.write_json(path, manifest)
        return path

    def read(self, clock: FakeClock, **kwargs):
        return bridge.get_job(JOB_ID, clock=clock, sleep=clock.sleep, **kwargs)

    def test_default_zero_returns_immediately_without_sleeping(self):
        self.write_job("running")
        clock = FakeClock()

        job = self.read(clock, detail="compact")

        self.assertEqual(job["status"], "running")
        self.assertEqual(job["detail"], "compact")
        self.assertEqual(job["wait_seconds"], 0)
        self.assertEqual(job["waited_seconds"], 0.0)
        self.assertFalse(job["wait_expired"])
        self.assertEqual(clock.sleeps, [])

    def test_terminal_status_returns_immediately(self):
        clock = FakeClock()
        for status in bridge.TERMINAL_JOB_STATUSES:
            with self.subTest(status=status):
                self.write_job(status)

                job = self.read(clock, wait_seconds=30)

                self.assertEqual(job["status"], status)
                self.assertEqual(job["wait_seconds"], 30)
                self.assertEqual(job["waited_seconds"], 0.0)
                self.assertFalse(job["wait_expired"])
                self.assertEqual(clock.sleeps, [])

    def test_running_job_returns_at_wait_expiry_without_claiming_completion(self):
        path = self.write_job("running")
        before = path.read_bytes()
        clock = FakeClock()

        job = self.read(clock, wait_seconds=1)

        self.assertEqual(job["status"], "running")
        self.assertEqual(job["wait_seconds"], 1)
        self.assertEqual(job["waited_seconds"], 1.0)
        self.assertTrue(job["wait_expired"])
        self.assertTrue(clock.sleeps)
        self.assertEqual(sum(clock.sleeps), 1.0)
        self.assertEqual(path.read_bytes(), before)

    def test_wait_returns_as_soon_as_the_job_finishes(self):
        self.write_job("running")
        clock = FakeClock(
            on_sleep=lambda count, _: self.write_job("succeeded") if count == 2 else None
        )

        job = self.read(clock, wait_seconds=2)

        self.assertEqual(job["status"], "succeeded")
        self.assertFalse(job["wait_expired"])
        self.assertLess(job["waited_seconds"], 2)
        self.assertEqual(len(clock.sleeps), 2)

    def test_invalid_wait_seconds_is_rejected_before_reading_the_job(self):
        self.write_job("running")
        for value in (1.0, 0.0, -1, 301, True, "5", None):
            with self.subTest(value=value):
                with patch.object(bridge, "job_path", side_effect=AssertionError("job read")):
                    with self.assertRaises(ValueError) as caught:
                        bridge.get_job(JOB_ID, wait_seconds=value)
                self.assertIn("wait_seconds", str(caught.exception))

    def test_wait_does_not_submit_or_take_the_toolkit_channel(self):
        path = self.write_job("running")
        before = path.read_bytes()
        clock = FakeClock()
        with (
            patch.object(bridge, "toolkit_lock") as lock,
            patch.object(bridge.subprocess, "Popen") as popen,
        ):
            job = self.read(clock, wait_seconds=1)

        lock.assert_not_called()
        popen.assert_not_called()
        self.assertTrue(job["wait_expired"])
        self.assertEqual(path.read_bytes(), before)

    def test_interruption_ends_only_the_wait(self):
        path = self.write_job("running")
        before = path.read_bytes()

        class InterruptedClock(FakeClock):
            def sleep(self, seconds):
                raise KeyboardInterrupt

        with (
            patch.object(bridge, "toolkit_lock") as lock,
            patch.object(bridge.subprocess, "Popen") as popen,
        ):
            with self.assertRaises(KeyboardInterrupt):
                self.read(InterruptedClock(), wait_seconds=30)

        lock.assert_not_called()
        popen.assert_not_called()
        self.assertEqual(path.read_bytes(), before)
        after = bridge.get_job(JOB_ID, clock=FakeClock())
        self.assertEqual(after["status"], "running")
        self.assertFalse(after["wait_expired"])

    def test_concurrent_waiters_are_independent(self):
        self.write_job("running", job_id=JOB_ID)
        self.write_job("succeeded", job_id=OTHER_JOB_ID)

        def wait(job_id, wait_seconds):
            clock = FakeClock()
            return job_id, bridge.get_job(
                job_id, clock=clock, sleep=clock.sleep, wait_seconds=wait_seconds
            )

        with ThreadPoolExecutor(max_workers=2) as pool:
            futures = [pool.submit(wait, JOB_ID, 1), pool.submit(wait, OTHER_JOB_ID, 30)]
            results = dict(future.result() for future in futures)

        self.assertEqual(results[JOB_ID]["status"], "running")
        self.assertTrue(results[JOB_ID]["wait_expired"])
        self.assertEqual(results[OTHER_JOB_ID]["status"], "succeeded")
        self.assertFalse(results[OTHER_JOB_ID]["wait_expired"])

    def test_server_forwards_wait_seconds(self):
        import server

        captured = {}

        def fake_get_job(*args, **kwargs):
            captured["args"] = args
            return {"status": "succeeded", "wait_seconds": args[6]}

        with patch.object(bridge, "get_job", side_effect=fake_get_job):
            result = asyncio.run(server.creo_get_job(JOB_ID, "compact", None, 50, None, None, 7))

        self.assertEqual(captured["args"][6], 7)
        self.assertEqual(result["wait_seconds"], 7)


if __name__ == "__main__":
    unittest.main()
