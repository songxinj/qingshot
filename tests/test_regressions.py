"""Failure paths from the code review, with unchanged normal product flows."""

import io
import json
import os
import subprocess
import sys
import threading
import time
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock, patch
from uuid import uuid4

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
os.environ.setdefault(
    "QINGSHOT_DATA",
    str(Path(__file__).resolve().parents[1] / "test-artifacts" / f"regressions-{uuid4().hex}"),
)

from PySide6.QtCore import QCoreApplication, QEvent, QPoint, QRect, Qt
from PySide6.QtGui import QPixmap
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication, QDialog, QLabel
from shiboken6 import isValid

from qingshot import translation
from qingshot.main_window import MainWindow
from qingshot.ocr import OcrBlock, reconstruct_layout
from qingshot.overlay import CaptureOverlay
from qingshot.paths import DATA
from qingshot.storage import Preferences
from qingshot.translation_dialog import TranslationDialog


class ReviewRegressionTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def window(self, preferences=None, register=None):
        fake = SimpleNamespace(
            RegisterHotKey=register or Mock(return_value=1),
            UnregisterHotKey=Mock(return_value=1),
        )
        windows = patch("qingshot.hotkey.ctypes.windll.user32", fake)
        settings = patch(
            "qingshot.storage.SettingsStore.load", return_value=preferences or Preferences()
        )
        saves = patch("qingshot.storage.SettingsStore.save")
        windows.start()
        settings.start()
        saved = saves.start()
        window = MainWindow()

        def cleanup():
            while window.runner.pending:
                QTest.qWait(5)
            window.hotkey.unregister()
            window.tray.hide()
            window.hide()
            saves.stop()
            settings.stop()
            windows.stop()

        self.addCleanup(cleanup)
        return window, saved

    def test_provider_route_stays_google_then_mymemory_and_disclosure_names_both(self):
        dialog = TranslationDialog(text="sample")
        self.addCleanup(dialog.close)
        text = " ".join(label.text() for label in dialog.findChildren(QLabel))
        self.assertIn("Google", text)
        self.assertIn("MyMemory", text)
        google = io.BytesIO(json.dumps([[["translated", "sample"]]]).encode())
        with patch("qingshot.translation.urllib.request.urlopen", return_value=google) as open_url:
            result = translation._request_translation("sample", "en", "zh-CN", time.monotonic() + 5)
        self.assertEqual(result, "translated")
        self.assertIn("translate.googleapis.com", open_url.call_args.args[0].full_url)
        self.assertEqual(result.providers, ("Google",))

        from urllib.error import URLError

        response = io.BytesIO(
            json.dumps(
                {"responseStatus": 200, "responseData": {"translatedText": "fallback"}}
            ).encode()
        )
        with patch(
            "qingshot.translation.urllib.request.urlopen",
            side_effect=[URLError("offline"), response],
        ) as open_url:
            result = translation._request_translation("sample", "en", "zh-CN", time.monotonic() + 5)
        self.assertEqual(result, "fallback")
        self.assertEqual(result.providers, ("MyMemory",))
        self.assertIn("api.mymemory.translated.net", open_url.call_args.args[0].full_url)

    def test_translation_result_keeps_actual_provider_through_gui_callback(self):
        answer = translation.TranslationText("translated", ("Google",))
        with patch("qingshot.translation._request_translation", return_value=answer):
            result = translation.translate("sample", "en", "zh-CN")
        self.assertEqual(result.providers, ("Google",))
        runner = SimpleNamespace(submit=Mock(return_value=True))
        dialog = TranslationDialog(text="sample", runner=runner)
        dialog.do_translate()
        runner.submit.call_args.args[1](result)
        self.assertEqual(dialog.result.toPlainText(), "translated")
        self.assertIn("Google", dialog.status.text())
        self.assertNotIn("MyMemory", dialog.status.text())
        dialog.close()

    def test_busy_dialog_reject_accept_and_escape_preserve_task_receiver(self):
        runner = SimpleNamespace(submit=Mock(return_value=True))
        dialog = TranslationDialog(text="sample", runner=runner)
        dialog.show()
        self.app.processEvents()
        dialog.do_translate()
        done = runner.submit.call_args.args[1]
        for close in [
            lambda: QTest.keyClick(dialog, Qt.Key_Escape),
            dialog.reject,
            dialog.accept,
            lambda: dialog.done(QDialog.Rejected),
            dialog.close,
        ]:
            close()
            QCoreApplication.sendPostedEvents(None, QEvent.DeferredDelete)
            self.assertTrue(isValid(dialog))
            self.assertTrue(dialog.isVisible())
        done("translated")
        self.assertFalse(dialog.busy)
        self.assertEqual(dialog.result.toPlainText(), "translated")
        dialog.close()

    def test_destroyed_dialog_ignores_late_callback(self):
        runner = SimpleNamespace(submit=Mock(return_value=True))
        dialog = TranslationDialog(text="sample", runner=runner)
        dialog.do_translate()
        done = runner.submit.call_args.args[1]
        dialog.deleteLater()
        QCoreApplication.sendPostedEvents(None, QEvent.DeferredDelete)
        self.assertFalse(isValid(dialog))
        done("translated")

    def test_special_shortcuts_execute_after_record_save_and_reload(self):
        from qingshot.storage import SettingsStore

        for sequence, key, modifiers in [
            ("PrintScreen", Qt.Key_Print, Qt.NoModifier),
            ("Ctrl+PageUp", Qt.Key_PageUp, Qt.ControlModifier),
            ("Ctrl+PageDown", Qt.Key_PageDown, Qt.ControlModifier),
            ("Win+A", Qt.Key_A, Qt.MetaModifier),
        ]:
            with self.subTest(sequence=sequence):
                store = SettingsStore(DATA / f"special-{uuid4().hex}.json")
                store.save(Preferences(copy_shortcut=sequence))
                image = QPixmap(600, 400)
                image.fill(Qt.white)
                overlay = CaptureOverlay(image, QRect(0, 0, 600, 400), store.load())
                overlay.selection = QRect(40, 40, 400, 200)
                events = []
                overlay.completed.connect(
                    lambda image, action, point, captured=events: captured.append(action)
                )
                overlay.show()
                overlay.activateWindow()
                overlay.setFocus()
                self.app.processEvents()
                QTest.keyClick(overlay, key, modifiers)
                self.assertEqual(events, ["copy"])
                overlay.close()

    def test_reset_to_occupied_default_saves_actual_restored_binding(self):
        window, saved = self.window(Preferences(hotkey="Ctrl+Alt+Q"), Mock(side_effect=[1, 0, 1]))
        window.reset_shortcuts()
        self.assertTrue(window.hotkey.registered)
        self.assertEqual(window.hotkey.shortcut, "Ctrl+Alt+Q")
        self.assertEqual(window.hotkey_input.shortcut(), "Ctrl+Alt+Q")
        self.assertEqual(window.preferences.hotkey, "Ctrl+Alt+Q")
        self.assertEqual(saved.call_args.args[0].hotkey, "Ctrl+Alt+Q")
        self.assertEqual(window.preferences.pin_shortcut, "Ctrl+P")

    def test_full_save_queue_keeps_failure_visible_after_copy(self):
        window, _ = self.window()
        while window.runner.pending:
            QTest.qWait(5)
        real_runner = window.runner

        def reject(function, on_done, on_error):
            on_error("queue full")
            return False

        window.runner = SimpleNamespace(submit=reject)
        image = QPixmap(80, 60)
        image.fill(Qt.white)
        window.was_visible = False
        try:
            window.consume_capture(image, "copy", QPoint())
            self.assertIn("未保存", window.status.text())
            self.assertIn("queue full", window.status.text())
            self.assertFalse(self.app.clipboard().pixmap().isNull())
        finally:
            window.runner = real_runner

    def test_timeout_returns_before_running_requests_and_global_concurrency_is_bounded(self):
        release = threading.Event()
        started = threading.Event()
        lock = threading.Lock()
        running = peak = 0

        def slow(*args):
            nonlocal running, peak
            with lock:
                running += 1
                peak = max(peak, running)
            started.set()
            release.wait(1)
            with lock:
                running -= 1
            return "translated"

        try:
            with (
                patch.object(translation, "TOTAL_TIMEOUT_SECONDS", 0.025),
                patch.object(translation, "_request_translation", side_effect=slow),
            ):
                for _ in range(4):
                    before = time.monotonic()
                    with self.assertRaises(RuntimeError):
                        translation.translate("sample", "en", "zh-CN")
                    self.assertLess(time.monotonic() - before, 0.2)
                self.assertTrue(started.is_set())
                self.assertLessEqual(peak, translation.MAX_PARALLEL_REQUESTS)
        finally:
            release.set()
        deadline = time.monotonic() + 1
        while running and time.monotonic() < deadline:
            time.sleep(0.005)
        self.assertEqual(running, 0)

    def test_instance_lock_excludes_second_process_and_allows_restart(self):
        from qingshot.instance import acquire_instance_lock

        path = DATA / f"instance-{uuid4().hex}.lock"
        owner = acquire_instance_lock("review", path)
        self.assertIsNotNone(owner)
        code = (
            "from pathlib import Path; from qingshot.instance import acquire_instance_lock; "
            "import sys; lock=acquire_instance_lock('review',Path(sys.argv[1])); "
            "print('owner' if lock is not None else 'secondary')"
        )
        try:
            child = subprocess.run(
                [sys.executable, "-c", code, str(path)],
                capture_output=True,
                text=True,
                encoding="utf-8",
                timeout=3,
            )
            self.assertEqual(child.returncode, 0, child.stderr)
            self.assertEqual(child.stdout.strip(), "secondary")
        finally:
            owner.unlock()
        restarted = acquire_instance_lock("review", path)
        self.assertIsNotNone(restarted)
        restarted.unlock()

    def test_ocr_join_handles_fragments_punctuation_and_real_word_gaps(self):
        for left, right, gap, expected in [
            ("Di", "rect", 0, "Direct"),
            ("Hello", ",", 2, "Hello,"),
            ("Hello", "world", 8, "Hello world"),
        ]:
            blocks = [OcrBlock(0, 0, 50, 20, left), OcrBlock(50 + gap, 0, 100, 20, right)]
            self.assertEqual(reconstruct_layout(blocks), expected)

    def test_reflow_preserves_arbitrary_numbered_and_lettered_lists(self):
        for marker in ["4.", "12.", "4)", "a)", "(iv)"]:
            text = f"3. Review all configuration settings before deployment\n{marker} Restart app"
            self.assertEqual(translation.merge_wrapped_lines(text, "en", "zh-CN"), text)


if __name__ == "__main__":
    unittest.main(verbosity=2)
