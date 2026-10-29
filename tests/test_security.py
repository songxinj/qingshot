"""Privacy regression checks for OCR initialization."""

import sys
import unittest
from pathlib import Path
from types import ModuleType
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from qingshot import ocr


class OcrPrivacyTests(unittest.TestCase):
    def test_telemetry_is_disabled_before_creating_cached_engine(self):
        events = []
        engine = object()
        runtime = ModuleType("onnxruntime")
        runtime.disable_telemetry_events = lambda: events.append("disable-telemetry")
        rapid = ModuleType("rapidocr_onnxruntime")

        def create_engine():
            events.append("create-engine")
            return engine

        rapid.RapidOCR = create_engine
        with (
            patch.dict(sys.modules, onnxruntime=runtime, rapidocr_onnxruntime=rapid),
            patch.object(ocr, "_RAPID_ENGINE", None),
        ):
            self.assertIs(ocr._get_rapid_ocr(), engine)
            self.assertIs(ocr._get_rapid_ocr(), engine)
        self.assertEqual(events, ["disable-telemetry", "create-engine"])


if __name__ == "__main__":
    unittest.main()
