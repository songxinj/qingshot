"""Local Windows OCR and an explicit, text-only online translation service."""

from __future__ import annotations

import html
import json
import re
import threading
import time
import urllib.error
import urllib.parse
import urllib.request
from concurrent.futures import FIRST_COMPLETED, ThreadPoolExecutor, wait

LANGUAGES = {
    "中文": "zh-CN",
    "English": "en",
    "日本語": "ja",
    "한국어": "ko",
    "Français": "fr",
    "Deutsch": "de",
    "Español": "es",
}
MAX_TEXT_BYTES = 12000
REQUEST_TIMEOUT_SECONDS = 18
TOTAL_TIMEOUT_SECONDS = 60
MAX_PARALLEL_REQUESTS = 3
SENTENCE_ENDINGS = (".", "!", "?", ":", ";", "。", "！", "？", "：", "；")
SENTENCE_SPLIT_RE = re.compile(r"(?<=[.!?。！？；;\n])\s+")
LIST_ITEM_RE = re.compile(r"^(?:\d+[.)]|[A-Za-z][.)]|\([A-Za-z0-9]+\))\s")
_HTTP_POOL = ThreadPoolExecutor(max_workers=MAX_PARALLEL_REQUESTS, thread_name_prefix="translation")
_HTTP_SLOTS = threading.BoundedSemaphore(MAX_PARALLEL_REQUESTS)


class TranslationText(str):
    """Keep the text API while carrying the actual service used for each result."""

    providers: tuple[str, ...]

    def __new__(cls, value: str, providers: tuple[str, ...] = ()) -> TranslationText:
        result = super().__new__(cls, value)
        result.providers = providers
        return result


def split_utf8(text: str, limit: int = 480) -> list[str]:
    """Keep every code point and enforce the provider's UTF-8 byte limit, preferring sentence boundaries."""
    if not text:
        return []
    if len(text.encode("utf-8")) <= limit:
        return [text]
    chunks: list[str] = []
    remaining = text
    while remaining:
        if len(remaining.encode("utf-8")) <= limit:
            chunks.append(remaining)
            break
        chunk = ""
        size = 0
        last_sentence_end = 0
        last_space = 0
        for idx, char in enumerate(remaining):
            n = len(char.encode("utf-8"))
            if size + n > limit:
                break
            chunk += char
            size += n
            if char in ".!?。！？；;\n":
                last_sentence_end = idx + 1
            elif char.isspace():
                last_space = idx + 1
        cut = (
            last_sentence_end
            if last_sentence_end >= len(chunk) // 2
            else (last_space if last_space >= len(chunk) // 2 else len(chunk))
        )
        chunks.append(remaining[:cut])
        remaining = remaining[cut:]
    return chunks


def _should_merge_wrapped_line(prev: str, curr: str, source: str, target: str) -> bool:
    if not prev.strip() or not curr.strip():
        return False
    if prev != prev.lstrip() or curr != curr.lstrip():
        return False
    prev_clean = prev.rstrip()
    curr_clean = curr.lstrip()
    if len(prev_clean) < 32:
        return False
    if curr_clean.startswith(("-", "*", "•", "#")) or LIST_ITEM_RE.match(curr_clean):
        return False
    prev_lang = detect_language(prev_clean, target) if source == "auto" else source
    curr_lang = detect_language(curr_clean, target) if source == "auto" else source
    if prev_lang != curr_lang or prev_lang == target:
        return False
    if not prev_clean.endswith(SENTENCE_ENDINGS):
        return True
    return bool(curr_clean and curr_clean[0].islower())


def merge_wrapped_lines(text: str, source: str = "auto", target: str = "") -> str:
    """Reflow soft-wrapped OCR/PDF prose lines into full sentences while keeping layout."""
    tokens = re.split(r"(\r\n|\r|\n)", text)
    if len(tokens) < 3:
        return text
    out: list[str] = [tokens[0]]
    idx = 1
    while idx < len(tokens):
        sep = tokens[idx]
        next_line = tokens[idx + 1] if idx + 1 < len(tokens) else ""
        if _should_merge_wrapped_line(out[-1], next_line, source, target):
            prev_line = out[-1].rstrip()
            curr_line = next_line.lstrip()
            joiner = (
                ""
                if (
                    prev_line.endswith("-")
                    or (not prev_line[-1].isascii() and not curr_line[0].isascii())
                )
                else " "
            )
            out[-1] = prev_line + joiner + curr_line
        else:
            out.append(sep)
            out.append(next_line)
        idx += 2
    return "".join(out)


def detect_language(text: str, target: str = "") -> str:
    if re.search(r"[\u3040-\u30ff]", text):
        return "ja"
    if re.search(r"[\uac00-\ud7af]", text):
        return "ko"
    chinese = len(re.findall(r"[\u4e00-\u9fff]", text))
    latin = len(re.findall(r"[A-Za-z]", text))
    if chinese and latin:
        if target == "zh-CN":
            return "en"
        if target == "en":
            return "zh-CN"
    return "zh-CN" if chinese and chinese >= latin else "en"


def _parse_translation_payload(result: object) -> str:
    if isinstance(result, list) and result and isinstance(result[0], list):
        parts = [
            segment[0]
            for segment in result[0]
            if isinstance(segment, list) and segment and isinstance(segment[0], str)
        ]
        joined = "".join(parts).strip()
        if joined:
            return html.unescape(joined)
        raise RuntimeError("翻译服务未返回有效译文，请重试。")
    if not isinstance(result, dict):
        raise RuntimeError("翻译服务返回的数据格式不正确。")
    if str(result.get("responseStatus", 500)) != "200":
        raise RuntimeError(
            "翻译服务暂不可用或额度已用完：" + str(result.get("responseDetails", "未知错误"))
        )
    data = result.get("responseData")
    if not isinstance(data, dict):
        raise RuntimeError("翻译服务返回的数据格式不正确。")
    value = data.get("translatedText")
    if not isinstance(value, str) or not value:
        raise RuntimeError("翻译服务未返回有效译文，请重试。")
    return html.unescape(value)


def _request_translation(text: str, source: str, target: str, deadline: float) -> str:
    remaining = deadline - time.monotonic()
    if remaining <= 0:
        raise RuntimeError("本次翻译耗时过长，请缩短原文后重试。")
    timeout = min(REQUEST_TIMEOUT_SECONDS, remaining)
    gtx_query = urllib.parse.urlencode(
        {"client": "gtx", "sl": source, "tl": target, "dt": "t", "q": text}
    )
    gtx_request = urllib.request.Request(
        "https://translate.googleapis.com/translate_a/single?" + gtx_query,
        headers={"User-Agent": "QingShot/0.2", "Accept": "application/json"},
    )
    try:
        with urllib.request.urlopen(gtx_request, timeout=timeout) as response:
            return TranslationText(_parse_translation_payload(json.load(response)), ("Google",))
    except (urllib.error.URLError, TimeoutError):
        pass
    except (ValueError, UnicodeError) as exc:
        raise RuntimeError("翻译服务返回了无法解析的数据，请稍后重试。") from exc

    remaining = deadline - time.monotonic()
    if remaining <= 0:
        raise RuntimeError("本次翻译耗时过长，请缩短原文后重试。")
    mm_query = urllib.parse.urlencode({"q": text, "langpair": f"{source}|{target}"})
    mm_request = urllib.request.Request(
        "https://api.mymemory.translated.net/get?" + mm_query,
        headers={"User-Agent": "QingShot/0.2", "Accept": "application/json"},
    )
    try:
        with urllib.request.urlopen(
            mm_request, timeout=min(REQUEST_TIMEOUT_SECONDS, remaining)
        ) as response:
            return TranslationText(_parse_translation_payload(json.load(response)), ("MyMemory",))
    except (urllib.error.URLError, TimeoutError) as exc:
        raise RuntimeError("翻译服务连接失败，请检查网络后重试。") from exc
    except (ValueError, UnicodeError) as exc:
        raise RuntimeError("翻译服务返回了无法解析的数据，请稍后重试。") from exc


def translate(text: str, source: str, target: str) -> str:
    """Translate nonempty lines independently, retaining their layout and order.

    Auto detection is local to each line. This prevents a Chinese heading from
    making an English paragraph look like already-translated Chinese. Duplicate
    lines share one request; at most three requests are in flight at a time.
    """
    if not text.strip():
        raise ValueError("请先识别或输入需要翻译的文字。")
    if source == target:
        raise ValueError("原文语言与目标语言相同，请选择其他目标语言。")
    if len(text.encode("utf-8")) > MAX_TEXT_BYTES:
        raise ValueError("单次翻译请控制在 12 KB 文字以内。")
    normalized_text = merge_wrapped_lines(text, source, target)
    parts: list[str | tuple[str, str]] = []
    jobs: dict[tuple[str, str], None] = {}
    for line in re.split(r"(\r\n|\r|\n)", normalized_text):
        if not line.strip():
            parts.append(line)
            continue
        language = detect_language(line, target) if source == "auto" else source
        if language == target or not any(char.isalpha() for char in line):
            parts.append(line)
            continue
        for chunk in split_utf8(line):
            if not chunk.strip():
                parts.append(chunk)
                continue
            leading = chunk[: len(chunk) - len(chunk.lstrip())]
            trailing = chunk[len(chunk.rstrip()) :]
            core = chunk.strip()
            parts.append(leading)
            if core:
                key = (core, language)
                parts.append(key)
                jobs[key] = None
            parts.append(trailing)
    if not jobs:
        raise ValueError("原文已是目标语言，或没有可翻译的文字。请选择其他目标语言。")
    deadline = time.monotonic() + TOTAL_TIMEOUT_SECONDS
    values: dict[tuple[str, str], str] = {}
    iterator = iter(jobs)
    pending = {}

    def enqueue() -> None:
        key = next(iterator, None)
        if key is None:
            return
        if not _HTTP_SLOTS.acquire(blocking=False):
            raise RuntimeError("翻译请求仍在处理，请稍后重试。")
        try:
            future = _HTTP_POOL.submit(_request_translation, key[0], key[1], target, deadline)
        except Exception:
            _HTTP_SLOTS.release()
            raise
        future.add_done_callback(lambda _future: _HTTP_SLOTS.release())
        pending[future] = key

    try:
        for _ in range(min(MAX_PARALLEL_REQUESTS, len(jobs))):
            enqueue()
        while pending:
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                for future in pending:
                    future.cancel()
                raise RuntimeError("本次翻译耗时过长，请缩短原文后重试。")
            completed, _ = wait(pending, timeout=remaining, return_when=FIRST_COMPLETED)
            if not completed:
                raise RuntimeError("本次翻译耗时过长，请缩短原文后重试。")
            for future in completed:
                key = pending.pop(future)
                values[key] = future.result()
                enqueue()
    finally:
        # Do not wait for in-flight HTTP here. Their slots remain held until they
        # finish, so retrying after a timeout cannot spawn unbounded requests.
        for future in pending:
            future.cancel()
    result = "".join(values[part] if isinstance(part, tuple) else part for part in parts)
    if result.strip() == text.strip():
        raise RuntimeError("翻译服务返回了原文，未生成译文。请检查语言选择，或稍后重试。")
    providers = tuple(
        dict.fromkeys(p for value in values.values() for p in getattr(value, "providers", ()))
    )
    return TranslationText(result, providers)
