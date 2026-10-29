"""Behavior regressions for inline annotations, compact controls and pin menus."""

import os
import sys
import time
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtCore import QPoint, QPointF, QRect, Qt
from PySide6.QtGui import QColor, QPixmap
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication

from qingshot.main_window import MainWindow
from qingshot.overlay import CaptureOverlay
from qingshot.pin import PinWindow
from qingshot.preview import Preview
from qingshot.translation_dialog import TranslationDialog


class CaptureUITests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def overlay(self):
        canvas = QPixmap(1000, 700)
        canvas.fill(QColor("white"))
        overlay = CaptureOverlay(canvas, QRect(0, 0, 1000, 700))
        overlay.selection = QRect(100, 100, 650, 340)
        overlay.show()
        overlay.set_tool("text")
        self.app.processEvents()
        self.addCleanup(overlay.close)
        return overlay

    def test_text_is_edited_on_canvas_and_enter_only_commits_annotation(self):
        overlay = self.overlay()
        QTest.mouseClick(overlay, Qt.LeftButton, pos=QPoint(180, 180))
        self.assertIsNotNone(overlay.editor)
        self.assertEqual(QApplication.activeModalWidget(), None)
        QTest.keyClicks(overlay.editor, "First line")
        QTest.keyClick(overlay.editor, Qt.Key_Return, Qt.ShiftModifier)
        QTest.keyClicks(overlay.editor, "Second line")
        QTest.keyClick(overlay.editor, Qt.Key_Return)
        self.assertIsNone(overlay.editor)
        self.assertFalse(overlay.done)
        self.assertEqual(overlay.items[0]["text"], "First line\nSecond line")
        self.assertTrue(all(shortcut.isEnabled() for shortcut in overlay.shortcuts))

    def test_escape_discards_text_before_canceling_capture(self):
        overlay = self.overlay()
        overlay.start_text(QPoint(200, 200))
        overlay.editor.setPlainText("discard this")
        QTest.keyClick(overlay.editor, Qt.Key_Escape)
        self.assertIsNone(overlay.editor)
        self.assertEqual(overlay.items, [])
        self.assertFalse(overlay.done)
        QTest.keyClick(overlay, Qt.Key_Escape)
        self.assertTrue(overlay.done)

    def test_copy_while_typing_copies_text_without_finishing_capture(self):
        overlay = self.overlay()
        overlay.start_text(QPoint(200, 200))
        overlay.editor.setPlainText("draft text")
        overlay.editor.selectAll()
        QTest.keyClick(overlay.editor, Qt.Key_C, Qt.ControlModifier)
        self.assertEqual(self.app.clipboard().text(), "draft text")
        self.assertFalse(overlay.done)

    def test_finish_commits_pending_text_and_popups_fit_near_screen_edge(self):
        overlay = self.overlay()
        overlay.selection = QRect(350, 430, 600, 250)
        overlay.position_toolbar()
        self.assertTrue(overlay.rect().contains(overlay.toolbar.geometry()))
        self.assertTrue(overlay.rect().contains(overlay.options.geometry()))
        overlay.start_text(QPoint(450, 500))
        overlay.editor.setPlainText("saved")
        captured = []
        overlay.completed.connect(lambda image, action, position: captured.append((image, action)))
        overlay.finish("copy")
        self.assertEqual(overlay.items[0]["text"], "saved")
        self.assertEqual(captured[0][1], "copy")
        self.assertFalse(captured[0][0].isNull())

    def test_pin_menu_keyboard_action_uses_original_image(self):
        image = QPixmap(160, 90)
        image.fill(QColor("#123456"))
        pin = PinWindow(image)
        self.addCleanup(pin.close)
        menu = pin.create_menu()
        menu.popup(QPoint(50, 50))
        self.app.processEvents()
        menu.setActiveAction(menu.actions()[0])
        QTest.keyClick(menu, Qt.Key_Return)
        self.assertEqual(
            self.app.clipboard().pixmap().toImage().pixelColor(5, 5), QColor("#123456")
        )
        menu.close()

    def test_ocr_does_not_override_selected_target_language(self):
        image = QPixmap(100, 50)
        image.fill(QColor("white"))
        with patch("qingshot.translation_dialog.recognize", return_value="Hello world\n说明"):
            dialog = TranslationDialog(image)
            dialog.target.setCurrentIndex(dialog.target.findData("ja"))
            dialog.show()
            deadline = time.monotonic() + 5
            while not dialog.original.toPlainText() and time.monotonic() < deadline:
                QTest.qWait(20)
            self.assertEqual(dialog.target.currentData(), "ja")
            self.assertIn("Hello", dialog.original.toPlainText())
            dialog.close()

    def test_wechat_handle_cursors_tool_toggle_and_mosaic_cache(self):
        overlay = self.overlay()
        overlay.set_tool("select")
        QTest.mouseMove(overlay, QPoint(5, 5))
        QTest.mouseMove(overlay, overlay.selection.topLeft())
        self.assertEqual(overlay.cursor().shape(), Qt.SizeFDiagCursor)
        QTest.mouseMove(overlay, overlay.selection.center())
        self.assertEqual(overlay.cursor().shape(), Qt.SizeAllCursor)
        overlay.toggle_tool("rect")
        self.assertEqual(overlay.tool, "rect")
        overlay.toggle_tool("rect")
        self.assertEqual(overlay.tool, "select")
        overlay.set_tool("mosaic")
        QTest.mousePress(overlay, Qt.LeftButton, pos=QPoint(140, 140))
        QTest.mouseMove(overlay, QPoint(240, 220), 5)
        QTest.mouseRelease(overlay, Qt.LeftButton, pos=QPoint(240, 220))
        overlay.grab()
        self.assertIn("_mosaic_pixmap", overlay.items[-1])
        first_cached = overlay.items[-1]["_mosaic_pixmap"]
        overlay.grab()
        self.assertIs(overlay.items[-1]["_mosaic_pixmap"], first_cached)
        overlay.items[-1]["points"][-1] = QPointF(260, 230)
        overlay.grab()
        self.assertIsNot(overlay.items[-1]["_mosaic_pixmap"], first_cached)

    def test_preview_caches_high_dpi_pixmap_and_open_translation_updates_content(self):
        preview = Preview()
        preview.resize(400, 300)
        pixmap = QPixmap(600, 400)
        pixmap.setDevicePixelRatio(2.0)
        pixmap.fill(QColor("#123456"))
        preview.pixmap = pixmap
        preview.grab()
        self.assertIsNotNone(preview._scaled_cache)
        cached = preview._scaled_cache
        preview.grab()
        self.assertIs(preview._scaled_cache, cached)
        self.assertLessEqual(cached.deviceIndependentSize().width(), 368)

        window = MainWindow()
        self.addCleanup(window.hotkey.unregister)
        self.addCleanup(window.tray.hide)
        dialog = window.open_translation(text="first")
        self.assertEqual(dialog.original.toPlainText(), "first")
        same_dialog = window.open_translation(text="second")
        self.assertIs(dialog, same_dialog)
        self.assertEqual(dialog.original.toPlainText(), "second")
        dialog.close()

    def test_checkbox_checkmark_and_shortcut_customization(self):
        window = MainWindow()
        self.addCleanup(window.hotkey.unregister)
        self.addCleanup(window.tray.hide)
        window.pages.setCurrentIndex(2)
        window.show()
        self.app.processEvents()

        # Verify checked CheckBox renders white checkmark pixels inside green indicator
        checkbox_img = window.remember.grab().toImage()
        indicator_colors = {
            checkbox_img.pixelColor(x, y).name()
            for x in range(2, min(18, checkbox_img.width()))
            for y in range(2, min(20, checkbox_img.height()))
        }
        self.assertIn("#ffffff", indicator_colors)

        # Record a new global capture shortcut and a custom pin shortcut
        window.hotkey_input.setFocus()
        QTest.keyClick(
            window.hotkey_input,
            Qt.Key_Q,
            Qt.ControlModifier | Qt.AltModifier,
        )
        self.assertEqual(window.hotkey_input.shortcut(), "Ctrl+Alt+Q")
        self.assertEqual(window.preferences.hotkey, "Ctrl+Alt+Q")
        self.assertIn("Ctrl + Alt + Q", window.hotkey_label.text())

        window.pin_shortcut_input.setFocus()
        QTest.keyClick(
            window.pin_shortcut_input,
            Qt.Key_D,
            Qt.ControlModifier | Qt.ShiftModifier,
        )
        self.assertEqual(window.preferences.pin_shortcut, "Ctrl+Shift+D")

        # Record PrintScreen special key
        window.hotkey_input.setFocus()
        QTest.keyClick(window.hotkey_input, Qt.Key_Print)
        self.assertEqual(window.hotkey_input.shortcut(), "PrintScreen")
        self.assertEqual(window.preferences.hotkey, "PrintScreen")

        # Reject duplicate shortcut (Ctrl+Shift+D already used by pin_shortcut) and reserved Ctrl+Z
        window.copy_shortcut_input.setFocus()
        QTest.keyClick(
            window.copy_shortcut_input,
            Qt.Key_D,
            Qt.ControlModifier | Qt.ShiftModifier,
        )
        self.assertEqual(window.copy_shortcut_input.shortcut(), "Ctrl+C")
        self.assertEqual(window.preferences.copy_shortcut, "Ctrl+C")
        self.assertIn("冲突", window.shortcut_status.text())

        window.copy_shortcut_input.setFocus()
        QTest.keyClick(window.copy_shortcut_input, Qt.Key_Z, Qt.ControlModifier)
        self.assertEqual(window.copy_shortcut_input.shortcut(), "Ctrl+C")
        self.assertEqual(window.preferences.copy_shortcut, "Ctrl+C")

        # Verify failed RegisterHotKey rolls back to previous working hotkey without saving
        window.hotkey.rebind("Ctrl+Alt+A")
        with patch(
            "qingshot.hotkey.ctypes.windll.user32.RegisterHotKey",
            side_effect=[0, 1],
        ):
            window.on_hotkey_changed("Ctrl+Alt+B")
        self.assertTrue(window.hotkey.registered)
        self.assertEqual(window.hotkey.shortcut, "Ctrl+Alt+A")
        self.assertEqual(window.hotkey_input.shortcut(), "Ctrl+Alt+A")
        self.assertEqual(window.preferences.hotkey, "PrintScreen")

        # Reset shortcuts to default
        window.reset_shortcuts()
        self.assertEqual(window.preferences.hotkey, "Ctrl+Alt+A")
        self.assertEqual(window.preferences.pin_shortcut, "Ctrl+P")
        window.hide()

        # Verify translate button grays out and prevents duplicate clicks while translating
        calls = []

        def slow_translate(text, source, target):
            calls.append(text)
            time.sleep(0.12)
            return "你好"

        with patch("qingshot.translation_dialog.translate", side_effect=slow_translate):
            dialog = TranslationDialog(text="Hello")
            dialog.show()
            self.app.processEvents()
            QTest.mouseClick(dialog.translate_button, Qt.LeftButton)
            QTest.mouseClick(dialog.translate_button, Qt.LeftButton)
            self.assertFalse(dialog.translate_button.isEnabled())
            self.assertEqual(dialog.translate_button.text(), "正在翻译…")
            btn_color = dialog.translate_button.grab().toImage().pixelColor(10, 10).name()
            self.assertEqual(btn_color, "#d5ded9")
            deadline = time.monotonic() + 5
            while dialog.busy and time.monotonic() < deadline:
                QTest.qWait(20)
            self.assertEqual(len(calls), 1)
            self.assertTrue(dialog.translate_button.isEnabled())
            self.assertEqual(dialog.translate_button.text(), "翻译 →")
            dialog.close()

    def test_cancel_capture_does_not_popup_main_window_and_selection_drag_has_no_jitter(self):
        window = MainWindow()
        self.addCleanup(window.hotkey.unregister)
        self.addCleanup(window.tray.hide)
        window.show()
        self.app.processEvents()
        window.was_visible = True
        window.hide()
        window.capture_canceled()
        self.assertFalse(window.isVisible())

        # Verify 1.25 DPR selection drag does not shift or jitter background pixels
        ratio = 1.25
        canvas = QPixmap(round(400 * ratio), round(300 * ratio))
        canvas.setDevicePixelRatio(ratio)
        image = canvas.toImage()
        for x in range(image.width()):
            for y in range(image.height()):
                image.setPixelColor(
                    x, y, QColor((x * 37) % 255, (y * 53) % 255, ((x + y) * 19) % 255)
                )
        canvas = QPixmap.fromImage(image)
        canvas.setDevicePixelRatio(ratio)
        overlay = CaptureOverlay(canvas, QRect(0, 0, 400, 300))
        self.addCleanup(overlay.close)
        overlay.selection = QRect(60, 60, 200, 150)
        base_crop = overlay.grab().toImage().copy(100, 100, 60, 60)
        for dx in range(1, 4):
            for dw in range(1, 4):
                overlay.selection = QRect(60 + dx, 60, 200 + dw, 150)
                crop = overlay.grab().toImage().copy(100, 100, 60, 60)
                self.assertEqual(crop, base_crop)


if __name__ == "__main__":
    unittest.main(verbosity=2)
