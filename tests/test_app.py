"""Run: python test_app.py. Real OCR + HTTP: set QINGSHOT_INTEGRATION=1."""

import os
import sys
import time
import unittest
from datetime import datetime
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT / "src"))
os.environ["PYTHONPATH"] = str(PROJECT_ROOT / "src")

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
os.environ["QINGSHOT_DATA"] = str(
    Path(__file__).resolve().parents[1]
    / "test-artifacts"
    / datetime.now().strftime("run-%Y%m%d-%H%M%S-%f")
)

from PySide6.QtCore import QPoint, QPointF, QRect, Qt
from PySide6.QtGui import QColor, QFont, QFontDatabase, QPainter, QPixmap
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication

from qingshot.desktop import desktop_snapshot
from qingshot.images import png_bytes
from qingshot.main_window import MainWindow
from qingshot.ocr import recognize
from qingshot.overlay import CaptureOverlay
from qingshot.paths import DATA
from qingshot.pin import PinWindow
from qingshot.translation import detect_language, split_utf8, translate
from qingshot.translation_dialog import TranslationDialog
from qingshot.ui import STYLE


class CaptureTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])
        # The offscreen platform does not enumerate the Windows font database.
        for name in ["arial.ttf", "msyh.ttc"]:
            font = Path(os.environ.get("SystemRoot", "C:/Windows")) / "Fonts" / name
            if font.exists():
                QFontDatabase.addApplicationFont(str(font))
        cls.app.setStyleSheet(STYLE)
        DATA.mkdir(parents=True, exist_ok=True)

    def overlay(self, ratio=1.25):
        canvas = QPixmap(round(1200 * ratio), round(750 * ratio))
        canvas.setDevicePixelRatio(ratio)
        canvas.fill(QColor("white"))
        widget = CaptureOverlay(canvas, QRect(0, 0, 1200, 750))
        widget.show()
        self.app.processEvents()
        self.addCleanup(widget.close)
        return widget

    def wait_runner(self, runner):
        deadline = time.monotonic() + 5
        while runner.pending and time.monotonic() < deadline:
            QTest.qWait(20)
        self.assertEqual(runner.pending, 0)

    def test_selection_export_preserves_dpi_and_annotations(self):
        w = self.overlay()
        QTest.mousePress(w, Qt.LeftButton, pos=QPoint(100, 100))
        QTest.mouseMove(w, QPoint(700, 400), 5)
        QTest.mouseRelease(w, Qt.LeftButton, pos=QPoint(700, 400))
        self.assertEqual(w.selection, QRect(100, 100, 601, 301))
        w.set_tool("rect")
        QTest.mousePress(w, Qt.LeftButton, pos=QPoint(150, 150))
        QTest.mouseMove(w, QPoint(300, 250), 5)
        QTest.mouseRelease(w, Qt.LeftButton, pos=QPoint(300, 250))
        self.assertEqual(len(w.items), 1)
        image = w.result()
        self.assertEqual((image.width(), image.height()), (751, 376))
        self.assertEqual(image.devicePixelRatio(), 1.25)
        pixel = image.toImage().pixelColor(round(50 * 1.25), round(80 * 1.25))
        self.assertGreater(pixel.red(), pixel.green())
        self.assertTrue(image.save(str(DATA / "annotated-dpi.png")))
        w.undo()
        self.assertEqual(w.items, [])

    def test_desktop_composition_handles_negative_origin_and_mixed_dpi(self):
        def screen(geometry, ratio, color):
            pixmap = QPixmap(round(geometry.width() * ratio), round(geometry.height() * ratio))
            pixmap.setDevicePixelRatio(ratio)
            pixmap.fill(QColor(color))
            return SimpleNamespace(
                geometry=lambda: geometry,
                devicePixelRatio=lambda: ratio,
                grabWindow=lambda window_id: pixmap,
            )

        screens = [
            screen(QRect(-800, 0, 800, 600), 1, "red"),
            screen(QRect(0, 0, 1200, 800), 1.5, "blue"),
        ]
        with patch("qingshot.desktop.QApplication", SimpleNamespace(screens=lambda: screens)):
            canvas, bounds = desktop_snapshot()
        self.assertEqual(bounds, QRect(-800, 0, 2000, 800))
        self.assertEqual(canvas.devicePixelRatio(), 1.5)
        self.assertEqual((canvas.width(), canvas.height()), (3000, 1200))
        image = canvas.toImage()
        self.assertEqual(image.pixelColor(100, 100), QColor("red"))
        self.assertEqual(image.pixelColor(2990, 100), QColor("blue"))
        self.assertEqual(image.pixelColor(100, 1100), QColor("#18241d"))

    def test_desktop_capture_failure_is_explicit(self):
        screen = SimpleNamespace(
            geometry=lambda: QRect(0, 0, 400, 300),
            devicePixelRatio=lambda: 1,
            grabWindow=lambda window_id: QPixmap(),
        )
        with patch("qingshot.desktop.QApplication", SimpleNamespace(screens=lambda: [screen])):
            with self.assertRaisesRegex(RuntimeError, "无法读取屏幕"):
                desktop_snapshot()

    def test_move_keeps_annotations_aligned(self):
        w = self.overlay(1)
        w.selection = QRect(100, 100, 300, 200)
        w.items = [
            {
                "kind": "text",
                "points": [QPointF(150, 150)],
                "text": "hello",
                "width": 3,
                "color": QColor("red"),
            }
        ]
        QTest.mousePress(w, Qt.LeftButton, pos=QPoint(200, 200))
        QTest.mouseMove(w, QPoint(250, 240), 5)
        QTest.mouseRelease(w, Qt.LeftButton, pos=QPoint(250, 240))
        self.assertEqual(w.selection.topLeft(), QPoint(150, 140))
        self.assertEqual(w.items[0]["points"][0], QPointF(200, 190))

    def test_mosaic_changes_source_pixels(self):
        w = self.overlay(1)
        p = QPainter(w.canvas)
        for x in range(1200):
            p.setPen(QColor("black") if x % 2 else QColor("white"))
            p.drawLine(x, 0, x, 749)
        p.end()
        w.selection = QRect(100, 100, 200, 150)
        w.items = [
            {
                "kind": "mosaic",
                "points": [QPointF(100, 100), QPointF(300, 250)],
                "width": 3,
                "color": QColor("red"),
            }
        ]
        img = w.result().toImage()
        self.assertEqual(img.pixelColor(20, 20), img.pixelColor(21, 20))

    def test_finish_emits_once_and_escape_cancels(self):
        w = self.overlay()
        w.selection = QRect(20, 20, 100, 80)
        events = []
        w.completed.connect(lambda image, action, position: events.append(action))
        QTest.keyClick(w, Qt.Key_Return)
        w.finish("copy")
        self.assertEqual(events, ["copy"])
        second = self.overlay()
        canceled = []
        second.canceled.connect(lambda: canceled.append(True))
        QTest.keyClick(second, Qt.Key_Escape)
        self.assertEqual(canceled, [True])

    def test_pin_keeps_original_for_copy(self):
        image = QPixmap(320, 180)
        image.fill(QColor("#123456"))
        pin = PinWindow(image)
        self.addCleanup(pin.close)
        pin.zoom = 2
        pin.resize_to_image()
        self.assertEqual(pin.size().width(), 640)
        pin.reset_zoom()
        self.assertEqual(pin.size().width(), 320)
        self.assertEqual(pin.pixmap.toImage().pixelColor(2, 2), QColor("#123456"))

    def test_main_history_settings_and_clipboard(self):
        w = MainWindow()
        self.addCleanup(w.hotkey.unregister)
        self.addCleanup(w.tray.hide)
        w.show()
        self.app.processEvents()
        self.assertIn("轻映", w.windowTitle())
        w.was_visible = False
        w.hidden_pins = []
        image = QPixmap(300, 200)
        image.fill(QColor("#334455"))
        w.consume_capture(image, "copy", QPoint(100, 100))
        self.wait_runner(w.runner)
        self.assertEqual(QApplication.clipboard().pixmap().size(), image.size())
        self.assertEqual(w.history.count(), 1)
        self.assertTrue(w.pin_button.isEnabled())
        w.remember.setChecked(False)
        self.assertTrue(w.settings_file.exists())
        w.hotkey.unregister()
        second = MainWindow()
        self.wait_runner(second.runner)
        self.addCleanup(second.hotkey.unregister)
        self.addCleanup(second.tray.hide)
        self.assertFalse(second.remember.isChecked())
        self.assertEqual(second.history.count(), 1)
        w.grab().save(str(DATA / "workspace.png"))
        w.hide()
        second.hide()

    def test_translation_dialog_text_flow(self):
        d = TranslationDialog(text="Hello world")
        self.assertEqual(d.original.toPlainText(), "Hello world")
        self.assertFalse(d.ocr_button.isEnabled())
        self.assertEqual(d.target.currentData(), "zh-CN")
        d.result.setPlainText("你好世界")
        d.copy_result()
        self.assertEqual(QApplication.clipboard().text(), "你好世界")
        d.close()

    def test_utf8_chunking_and_language_detection(self):
        original = "你好世界 🌍\n" * 100
        chunks = split_utf8(original)
        self.assertEqual("".join(chunks), original)
        self.assertTrue(all(len(c.encode("utf-8")) <= 480 for c in chunks))
        self.assertEqual(detect_language("こんにちは"), "ja")
        self.assertEqual(detect_language("안녕하세요"), "ko")
        self.assertEqual(detect_language("你好 world"), "en")
        self.assertEqual(detect_language("你好，世界"), "zh-CN")
        self.assertEqual(detect_language("hello"), "en")
        with self.assertRaisesRegex(ValueError, "相同"):
            translate("same", "en", "en")
        with self.assertRaises(ValueError):
            translate(" ", "en", "zh-CN")

    @unittest.skipUnless(os.environ.get("QINGSHOT_INTEGRATION") == "1", "integration opt-in")
    def test_real_windows_ocr_and_online_translation(self):
        pixmap = QPixmap(700, 160)
        pixmap.fill(Qt.white)
        p = QPainter(pixmap)
        p.setFont(QFont("Arial", 30))
        p.setPen(Qt.black)
        p.drawText(25, 90, "Hello world 12345")
        p.end()
        pixmap.save(str(DATA / "ocr-source.png"))
        text = recognize(png_bytes(pixmap))
        self.assertIn("Hello", text)
        self.assertIn("12345", text)
        result = translate("Hello world", "en", "zh-CN")
        self.assertTrue(any("\u4e00" <= c <= "\u9fff" for c in result))


if __name__ == "__main__":
    unittest.main(verbosity=2)
