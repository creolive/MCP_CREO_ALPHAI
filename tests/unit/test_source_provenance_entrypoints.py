"""Report construction must consume provenance without starting a real client."""

import asyncio
import contextlib
import io
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from creo_mechdog import source_provenance
from tools import test_sketch_geometry_deviation as deviation
from tools import test_startup_retry as startup
from tools import test_toolkit_channel as channel
from tools import test_toolkit_recovery as recovery

IDENTITY = {"source_commit": "b" * 40, "dirty": False, "git_status": "available"}


class ReportEntrypointTests(unittest.TestCase):
    def test_recovery_report_consumes_source_commit_before_any_native_work(self):
        with (
            tempfile.TemporaryDirectory() as directory,
            patch.object(recovery, "provenance", return_value=IDENTITY),
            patch.object(recovery.bridge, "config", return_value={"creo_root": "fixture"}),
            patch.object(recovery, "native") as native,
            patch.object(recovery, "controlled") as controlled,
            contextlib.redirect_stdout(io.StringIO()),
        ):
            args = SimpleNamespace(
                output=Path(directory) / "report.json", native=False, controlled=False
            )
            report = asyncio.run(recovery.run(args))
        native.assert_not_called()
        controlled.assert_not_called()
        self.assertEqual(report["source_commit"], "b" * 40)

    def test_channel_report_consumes_source_commit_before_client_creation(self):
        with (
            tempfile.TemporaryDirectory() as directory,
            patch.object(channel, "provenance", return_value=IDENTITY),
            patch.object(channel, "Client", side_effect=RuntimeError("offline sentinel")) as client,
            contextlib.redirect_stdout(io.StringIO()),
        ):
            report = asyncio.run(channel.run(Path(directory) / "report.json", 0, []))
        self.assertEqual(report["source_commit"], "b" * 40)
        self.assertIn("offline sentinel", report["failure"])
        client.assert_called_once()

    def test_startup_report_consumes_source_commit_before_client_creation(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            for name in (
                "bridge.py",
                "generic_bridge.py",
                "creo_startup.py",
                "server.py",
                "src/creo_mechdog/startup_state.py",
                "src/creo_mechdog/windows_boot.py",
                "src/creo_mechdog/recovery.py",
                "native/worker.cpp",
                "native/result_delivery.h",
                "tools/test_startup_retry.py",
                "build/creo_worker.exe",
            ):
                p = root / name
                p.parent.mkdir(parents=True, exist_ok=True)
                p.write_bytes(b"fixture")
            with (
                patch.object(startup, "ROOT", root),
                patch.object(startup, "provenance", return_value=IDENTITY),
                patch.object(startup.bridge, "config", return_value={"creo_root": "fixture"}),
                patch.object(startup.creo_startup.Settings, "load", return_value=SimpleNamespace()),
                patch.object(
                    startup.creo_startup,
                    "inventory",
                    return_value={"uncertain": False, "processes": []},
                ),
                patch.object(
                    startup.creo_startup,
                    "CreoStartup",
                    return_value=SimpleNamespace(_target_directory=lambda _: root / "startup"),
                ),
                patch.object(startup.creo_startup, "windows_session", return_value=1),
                patch.object(startup, "protected_files", return_value={}),
                patch.object(
                    startup, "Client", side_effect=RuntimeError("offline sentinel")
                ) as client,
                contextlib.redirect_stdout(io.StringIO()),
            ):
                report = asyncio.run(
                    startup.run(SimpleNamespace(require_cold=False, output=root / "report.json"))
                )
        self.assertEqual(report["source_commit"], "b" * 40)
        self.assertIn("offline sentinel", report["failure"])
        client.assert_called_once()

    def test_partial_source_evidence_survives_report_projection(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            p = root / "tools/test_sketch_geometry_deviation.py"
            p.parent.mkdir(parents=True)
            p.write_text("# fixture", encoding="utf-8")
            with (
                patch.object(deviation, "ROOT", root),
                patch.object(source_provenance.shutil, "which", return_value=None),
            ):
                report = deviation.provenance()
        self.assertIsNone(report["source_fingerprint"])
        self.assertEqual(report["source_status"], "incomplete")
        self.assertEqual(report["source_scope"], "distributed_source")
        self.assertEqual(report["source_file_count"], 1)
        self.assertEqual(
            report["source_errors"][0]["path"], "tests/unit/test_sketch_geometry_deviation.py"
        )
