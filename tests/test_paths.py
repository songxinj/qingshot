"""Check real process data routing after the QingShot rename."""

import json
import os
import subprocess
import sys
import unittest
from pathlib import Path
from uuid import uuid4

PROJECT = Path(__file__).resolve().parents[1]
CHILD = """
import json
import os
from unittest.mock import patch

if os.environ.get('QINGSHOT_TEST_INSTALLED') == '1':
    with patch('pathlib.Path.is_file', return_value=False):
        from qingshot.paths import DATA
else:
    from qingshot.paths import DATA
print(json.dumps(str(DATA)))
"""


class DataPathCompatibilityTests(unittest.TestCase):
    def setUp(self):
        self.root = PROJECT / "test-artifacts" / f"paths-{uuid4().hex}"
        self.local_data = self.root / "local-app-data"
        self.local_data.mkdir(parents=True)

    def read_path(self, *, installed=False, **overrides):
        env = {
            key: value
            for key, value in os.environ.items()
            if key not in {"QINGSHOT_DATA", "QINGCAPTURE_DATA", "QINGSHOT_TEST_INSTALLED"}
        }
        env.update(
            PYTHONPATH=str(PROJECT / "src"),
            PYTHONDONTWRITEBYTECODE="1",
            LOCALAPPDATA=str(self.local_data),
            QINGSHOT_TEST_INSTALLED="1" if installed else "0",
            **{key: str(value) for key, value in overrides.items()},
        )
        result = subprocess.run(
            [sys.executable, "-B", "-c", CHILD],
            env=env,
            capture_output=True,
            text=True,
            encoding="utf-8",
            timeout=3,
            check=True,
        )
        return Path(json.loads(result.stdout))

    def test_source_checkout_keeps_project_data(self):
        self.assertEqual(self.read_path(), PROJECT / "data")

    def test_fresh_install_uses_qingshot_directory(self):
        self.assertEqual(self.read_path(installed=True), self.local_data / "QingShot")

    def test_existing_install_keeps_legacy_directory(self):
        legacy = self.local_data / "QingCapture"
        legacy.mkdir()
        self.assertEqual(self.read_path(installed=True), legacy)

    def test_legacy_environment_override_remains_supported(self):
        legacy = self.root / "legacy-override"
        self.assertEqual(self.read_path(QINGCAPTURE_DATA=legacy), legacy)

    def test_new_environment_override_takes_precedence(self):
        preferred = self.root / "preferred-override"
        self.assertEqual(
            self.read_path(QINGSHOT_DATA=preferred, QINGCAPTURE_DATA=self.root / "old-override"),
            preferred,
        )


if __name__ == "__main__":
    unittest.main()
