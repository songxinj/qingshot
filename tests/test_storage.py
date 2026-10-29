"""Settings corruption, history bounds, provider errors, and GUI responsiveness."""

import io
import itertools
import json
import os
import sys
import threading
import time
import unittest
from pathlib import Path
from unittest.mock import patch
from uuid import uuid4

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtCore import QThread, QTimer
from PySide6.QtGui import QImage
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication

from qingshot.paths import DATA
from qingshot.storage import CaptureStore, Preferences, SettingsStore
from qingshot.translation import translate
from qingshot.workers import TaskRunner


class StorageTests(unittest.TestCase):
    def setUp(self):
        self.directory = DATA / f"storage-{uuid4().hex}"
        self.directory.mkdir(parents=True)

    def test_corrupt_and_wrong_type_settings_fall_back(self):
        store = SettingsStore(self.directory / "settings.json")
        for content in ["{broken", "[]", "null", '{"remember":"false","hide_to_tray":4}']:
            store.path.write_text(content, encoding="utf-8")
            self.assertEqual(store.load(), Preferences())
        self.assertTrue(store.path.exists())

    def test_atomic_settings_survive_a_fresh_store(self):
        path = self.directory / "settings.json"
        SettingsStore(path).save(Preferences(remember=False))
        self.assertFalse(SettingsStore(path).load().remember)
        self.assertTrue(SettingsStore(path).load().hide_to_tray)
        self.assertFalse(path.with_suffix(".pending").exists())

    def test_large_history_is_bounded_without_decoding(self):
        for index in range(600):
            (self.directory / f"20260101_000000_{index:06d}.png").touch()
        paths = CaptureStore(self.directory).recent(17)
        self.assertEqual(len(paths), 17)
        self.assertTrue(paths[0].name.endswith("000599.png"))
        self.assertTrue(paths[-1].name.endswith("000583.png"))

    def test_empty_image_save_fails_explicitly(self):
        with self.assertRaises(OSError):
            CaptureStore(self.directory).save(QImage())


class ProviderTests(unittest.TestCase):
    def test_invalid_json_and_payload_are_reported(self):
        for payload in [b"not-json", b"[]", b'{"responseStatus":200,"responseData":null}']:
            with (
                self.subTest(payload=payload),
                patch(
                    "qingshot.translation.urllib.request.urlopen",
                    return_value=io.BytesIO(payload),
                ),
                self.assertRaises(RuntimeError),
            ):
                translate("hello", "en", "zh-CN")

    def test_quota_response_is_reported(self):
        payload = json.dumps({"responseStatus": 429, "responseDetails": "quota"}).encode()
        with patch("qingshot.translation.urllib.request.urlopen", return_value=io.BytesIO(payload)):
            with self.assertRaisesRegex(RuntimeError, "quota"):
                translate("hello", "en", "zh-CN")

    def test_total_request_budget_stops_long_translations(self):
        with patch(
            "qingshot.translation.time.monotonic",
            side_effect=itertools.chain([0], itertools.repeat(61)),
        ):
            with self.assertRaisesRegex(RuntimeError, "耗时过长"):
                translate("hello", "en", "zh-CN")


class WorkerTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def test_workers_bound_concurrency_and_keep_gui_responsive(self):
        runner = TaskRunner()
        lock = threading.Lock()
        running = 0
        peak = 0
        callbacks = []
        ticks = []

        def work():
            nonlocal running, peak
            with lock:
                running += 1
                peak = max(peak, running)
            time.sleep(0.08)
            with lock:
                running -= 1
            return 42

        def done(result):
            callbacks.append((result, QThread.currentThread() == self.app.thread()))

        timer = QTimer()
        timer.setInterval(10)
        timer.timeout.connect(lambda: ticks.append(True))
        timer.start()
        for _ in range(4):
            self.assertTrue(runner.submit(work, done))
        deadline = time.monotonic() + 4
        while runner.pending and time.monotonic() < deadline:
            QTest.qWait(10)
        timer.stop()
        self.assertEqual(runner.pending, 0)
        self.assertEqual(callbacks, [(42, True)] * 4)
        self.assertLessEqual(peak, 2)
        self.assertGreater(len(ticks), 2)


if __name__ == "__main__":
    unittest.main(verbosity=2)
