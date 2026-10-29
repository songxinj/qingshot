"""Local OCR engine with in-memory RapidOCR singleton and layout reconstruction.

Uses RapidOCR (PP-OCRv4 ONNX) directly on in-memory PNG bytes as the primary
engine, with Windows.Media.Ocr via PowerShell as a fallback.
"""

from __future__ import annotations

import base64
import json
import os
import re
import statistics
import subprocess
import threading
from dataclasses import dataclass
from pathlib import Path

_ENGINE_LOCK = threading.Lock()
_RAPID_ENGINE = None

MIN_TEXT_SCORE = 0.55
SINGLE_CHAR_MIN_SCORE = 0.80

_CJK_CHAR = r"\u4e00-\u9fff\u3000-\u303f\uff00-\uffef"
_BOGUS_CJK_SPACE = re.compile(rf"(?<=[{_CJK_CHAR}]) (?=[{_CJK_CHAR}])")
_BROKEN_OCR_SUFFIX = re.compile(r"\b([A-Z][a-z]+)ocR\b")
_SENTENCE_END = (".", "!", "?", ":", ";", "。", "！", "？", "：", "；")


@dataclass(slots=True)
class OcrBlock:
    x0: float
    y0: float
    x1: float
    y1: float
    text: str
    score: float = 1.0

    @property
    def width(self) -> float:
        return max(1.0, self.x1 - self.x0)

    @property
    def height(self) -> float:
        return max(1.0, self.y1 - self.y0)

    @property
    def cy(self) -> float:
        return (self.y0 + self.y1) * 0.5


def _get_rapid_ocr():
    global _RAPID_ENGINE
    if _RAPID_ENGINE is not None:
        return _RAPID_ENGINE
    with _ENGINE_LOCK:
        if _RAPID_ENGINE is None:
            from rapidocr_onnxruntime import RapidOCR

            _RAPID_ENGINE = RapidOCR()
    return _RAPID_ENGINE


def clean_ocr_text(text: str) -> str:
    """Remove bogus single spaces between CJK characters while keeping layout."""
    cleaned_lines = []
    for line in text.splitlines():
        stripped = _BOGUS_CJK_SPACE.sub("", line.rstrip())
        stripped = _BROKEN_OCR_SUFFIX.sub(r"\1OCR", stripped)
        cleaned_lines.append(stripped)
    return "\n".join(cleaned_lines)


def _needs_space_between(left: str, right: str, gap: float, line_height: float) -> str:
    if not left or not right:
        return ""
    if gap > line_height * 1.8:
        return "    "
    left_char = left[-1]
    right_char = right[0]
    if left_char.isspace() or right_char.isspace():
        return ""
    if right_char in ",.:;!?)]}" or left_char in "([{":
        return ""
    if left_char.isascii() and right_char.isascii():
        if left_char.isalnum() and right_char.isalnum() and abs(gap) <= line_height * 0.1:
            return ""
        if left_char.isalnum() or left_char in ",.:;!?)]}" or right_char.isalnum():
            return " "
    if gap > line_height * 0.25:
        return " "
    return ""


def reconstruct_layout(blocks: list[OcrBlock]) -> str:
    """Group OCR blocks into visual rows and preserve horizontal and paragraph spacing."""
    valid = [
        b
        for b in blocks
        if b.text.strip()
        and b.score >= (SINGLE_CHAR_MIN_SCORE if len(b.text.strip()) == 1 else MIN_TEXT_SCORE)
    ]
    if not valid:
        return ""
    valid.sort(key=lambda b: (b.cy, b.x0))

    rows: list[list[OcrBlock]] = []
    for block in valid:
        if not rows:
            rows.append([block])
            continue
        current_row = rows[-1]
        row_cy = statistics.fmean(item.cy for item in current_row)
        row_height = statistics.fmean(item.height for item in current_row)
        if abs(block.cy - row_cy) <= max(row_height, block.height) * 0.55:
            current_row.append(block)
        else:
            rows.append([block])

    row_metrics: list[tuple[float, float, float, str]] = []
    for row in rows:
        row.sort(key=lambda b: b.x0)
        row_height = statistics.fmean(item.height for item in row)
        parts = [row[0].text.strip()]
        for prev, curr in zip(row, row[1:], strict=False):
            curr_text = curr.text.strip()
            sep = _needs_space_between(parts[-1], curr_text, curr.x0 - prev.x1, row_height)
            parts.append(sep + curr_text)
        line_text = clean_ocr_text("".join(parts))
        y0 = min(item.y0 for item in row)
        y1 = max(item.y1 for item in row)
        cy = (y0 + y1) * 0.5
        row_metrics.append((y0, y1, cy, line_text))

    if len(row_metrics) == 1:
        return row_metrics[0][3]

    heights = [y1 - y0 for y0, y1, _, _ in row_metrics]
    median_height = statistics.median(heights)
    dys = [row_metrics[i + 1][2] - row_metrics[i][2] for i in range(len(row_metrics) - 1)]
    normal_dys = [dy for dy in dys if dy <= median_height * 2.2] or dys
    baseline_dy = statistics.median(normal_dys)

    output_lines = [row_metrics[0][3]]
    for i in range(1, len(row_metrics)):
        prev_y0, prev_y1, prev_cy, _ = row_metrics[i - 1]
        curr_y0, curr_y1, curr_cy, curr_text = row_metrics[i]
        dy = curr_cy - prev_cy
        vertical_gap = curr_y0 - prev_y1
        if (
            len(row_metrics) >= 3
            and dy > baseline_dy * 1.32
            and vertical_gap > median_height * 0.65
        ):
            output_lines.append("")
        output_lines.append(curr_text)
    return "\n".join(output_lines)


def _recognize_with_rapidocr(png: bytes) -> str:
    engine = _get_rapid_ocr()
    raw_results, _ = engine(png, use_cls=False, unclip_ratio=2.2)
    if not raw_results:
        return ""
    blocks: list[OcrBlock] = []
    for box, text, score in raw_results:
        xs = [float(pt[0]) for pt in box]
        ys = [float(pt[1]) for pt in box]
        blocks.append(
            OcrBlock(
                x0=min(xs),
                y0=min(ys),
                x1=max(xs),
                y1=max(ys),
                text=str(text),
                score=float(score),
            )
        )
    return reconstruct_layout(blocks)


def _recognize_with_windows_ocr(png: bytes, language: str = "auto") -> str:
    payload = json.dumps({"image": base64.b64encode(png).decode("ascii"), "language": language})
    powershell = (
        Path(os.environ.get("SystemRoot", "C:/Windows"))
        / "System32/WindowsPowerShell/v1.0/powershell.exe"
    )
    try:
        process = subprocess.run(
            [
                str(powershell),
                "-NoProfile",
                "-NonInteractive",
                "-ExecutionPolicy",
                "Bypass",
                "-File",
                str(Path(__file__).with_name("resources") / "ocr.ps1"),
            ],
            input=payload,
            capture_output=True,
            encoding="utf-8",
            timeout=35,
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
        )
    except subprocess.TimeoutExpired as exc:
        raise RuntimeError("本地识字超时，请缩小截图范围后重试。") from exc
    try:
        result = json.loads(process.stdout.strip().lstrip("\ufeff"))
    except (ValueError, TypeError) as exc:
        raise RuntimeError("Windows OCR 启动失败，请检查 Windows 语言包。") from exc
    if not result.get("ok"):
        raise RuntimeError(result.get("error", "本地识字失败"))
    return clean_ocr_text(result.get("text", ""))


def recognize(png: bytes, language: str = "auto") -> str:
    if language in ("auto", "zh-CN", "en"):
        try:
            return _recognize_with_rapidocr(png)
        except ImportError:
            pass
        except Exception:
            if language != "auto":
                raise
    return _recognize_with_windows_ocr(png, language)
