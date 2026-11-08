"""The count gate must also run from an unpacked source distribution."""

import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


class BacklogCountsCliTest(unittest.TestCase):
    def test_isolated_copy_without_site_packages_still_exits_zero(self):
        root = Path(self.enterContext(tempfile.TemporaryDirectory()))
        (root / "tools").mkdir()
        (root / "src" / "creo_mechdog").mkdir(parents=True)
        (root / "docs").mkdir()
        shutil.copyfile(
            ROOT / "tools" / "check_backlog_counts.py",
            root / "tools" / "check_backlog_counts.py",
        )
        shutil.copyfile(
            ROOT / "src" / "creo_mechdog" / "backlog_counts.py",
            root / "src" / "creo_mechdog" / "backlog_counts.py",
        )
        shutil.copyfile(ROOT / "docs" / "BACKLOG.md", root / "docs" / "BACKLOG.md")
        result = subprocess.run(
            [sys.executable, "-I", "-S", str(root / "tools" / "check_backlog_counts.py")],
            capture_output=True,
            text=True,
            check=False,
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn('"consistent": true', result.stdout)


if __name__ == "__main__":
    unittest.main()
