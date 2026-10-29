"""Translation must produce real output and preserve multiline text layout."""

import os
import sys
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from qingshot.ocr import OcrBlock, clean_ocr_text, reconstruct_layout
from qingshot.translation import merge_wrapped_lines, translate


class MultilineTranslationTests(unittest.TestCase):
    def test_chinese_heading_does_not_bypass_english_translation(self):
        text = "Hello world.\nPlease save this image.\n说明"
        answers = {"Hello world.": "你好，世界。", "Please save this image.": "请保存这张图片。"}
        with patch(
            "qingshot.translation._request_translation",
            side_effect=lambda value, source, target, deadline: answers[value],
        ) as request:
            result = translate(text, "auto", "zh-CN")
        self.assertEqual(result, "你好，世界。\n请保存这张图片。\n说明")
        self.assertEqual(request.call_count, 2)

    def test_mixed_chinese_abbreviation_line_is_translated_to_english(self):
        recorded = []

        def fake_request(value, source, target, deadline):
            recorded.append((value, source, target))
            return "API description"

        with patch("qingshot.translation._request_translation", side_effect=fake_request):
            result = translate("API 说明", "auto", "en")
        self.assertEqual(result, "API description")
        self.assertEqual(recorded, [("API 说明", "zh-CN", "en")])

    def test_ocr_layout_reconstruction_merges_inline_code_and_preserves_paragraph_gap(self):
        blocks = [
            OcrBlock(21, 9, 525, 43, "Initial hypothesis: Implementing a singleton", 0.99),
            OcrBlock(515, 14, 731, 38, "RapidOCR instance", 0.97),
            OcrBlock(
                19,
                51,
                744,
                85,
                "with caching will drastically reduce initialization overhead. Direct",
                0.99,
            ),
            OcrBlock(
                18,
                89,
                677,
                126,
                "in-memory PNG processing eliminates disk I/O, optimizing",
                0.99,
            ),
            OcrBlock(
                20,
                134,
                758,
                164,
                "performance. Low-confidence score filtering is critical to eliminate",
                0.99,
            ),
            OcrBlock(21, 175, 229, 202, "noise from results.", 0.99),
            OcrBlock(
                21,
                230,
                752,
                261,
                "A layout reconstruction function will be essential for retaining the",
                1.00,
            ),
            OcrBlock(21, 270, 238, 304, "original formatting.", 0.99),
            OcrBlock(533, 498, 542, 506, "A", 0.61),  # low-confidence single-char noise
        ]
        reconstructed = reconstruct_layout(blocks)
        expected = (
            "Initial hypothesis: Implementing a singleton RapidOCR instance\n"
            "with caching will drastically reduce initialization overhead. Direct\n"
            "in-memory PNG processing eliminates disk I/O, optimizing\n"
            "performance. Low-confidence score filtering is critical to eliminate\n"
            "noise from results.\n\n"
            "A layout reconstruction function will be essential for retaining the\n"
            "original formatting."
        )
        self.assertEqual(reconstructed, expected)
        self.assertEqual(clean_ocr_text("截 图 ， 让 表 达 更 简 单 。"), "截图，让表达更简单。")
        reflowed = merge_wrapped_lines(reconstructed, "auto", "zh-CN")
        self.assertEqual(
            reflowed,
            (
                "Initial hypothesis: Implementing a singleton RapidOCR instance "
                "with caching will drastically reduce initialization overhead. Direct "
                "in-memory PNG processing eliminates disk I/O, optimizing "
                "performance. Low-confidence score filtering is critical to eliminate "
                "noise from results.\n\n"
                "A layout reconstruction function will be essential for retaining the "
                "original formatting."
            ),
        )

    def test_blank_lines_indentation_and_windows_newlines_survive(self):
        text = "  Hello world\r\n\r\n    Save image  \r\n"
        answers = {"Hello world": "你好世界", "Save image": "保存图片"}
        with patch(
            "qingshot.translation._request_translation",
            side_effect=lambda value, *args: answers[value],
        ):
            self.assertEqual(translate(text, "en", "zh-CN"), "  你好世界\r\n\r\n    保存图片  \r\n")

    def test_duplicate_lines_share_a_request(self):
        with patch("qingshot.translation._request_translation", return_value="你好") as request:
            result = translate("Hello\nHello\nHello", "en", "zh-CN")
        self.assertEqual(result, "你好\n你好\n你好")
        self.assertEqual(request.call_count, 1)

    def test_equal_languages_and_unchanged_provider_output_are_not_success(self):
        with self.assertRaisesRegex(ValueError, "相同"):
            translate("Hello", "en", "en")
        with self.assertRaises(ValueError):
            translate("你好\n说明", "auto", "zh-CN")
        with patch("qingshot.translation._request_translation", return_value="Hello"):
            with self.assertRaisesRegex(RuntimeError, "未生成译文"):
                translate("Hello", "en", "zh-CN")

    @unittest.skipUnless(os.environ.get("QINGSHOT_INTEGRATION") == "1", "integration opt-in")
    def test_real_mixed_multiline_translation(self):
        result = translate("Hello world.\nPlease save this image.\n说明", "auto", "zh-CN")
        self.assertEqual(len(result.splitlines()), 3)
        self.assertNotIn("Please save this image", result)
        self.assertEqual(result.splitlines()[2], "说明")
