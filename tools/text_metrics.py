#!/usr/bin/env python3
"""Deterministic, source-text-free text metrics for Malmatch.

The module accepts dialogue text while computing metrics, but it only returns
counts and line indexes. Source strings are never included in the result.
"""

from __future__ import annotations

import argparse
import json
import re
import unicodedata
from typing import Any


VERSION = "0.1.0"

LINE_BREAK_RE = re.compile(r"\r\n|\r|\n|\u2028|\u2029")
SPEAKER_PREFIX_RE = re.compile(r"^\s*[^:\n]{1,20}:\s*")

HANGUL_RANGES = (
    (0x1100, 0x11FF),  # Hangul Jamo
    (0x3130, 0x318F),  # Hangul Compatibility Jamo
    (0xA960, 0xA97F),  # Hangul Jamo Extended-A
    (0xAC00, 0xD7A3),  # Hangul Syllables
    (0xD7B0, 0xD7FF),  # Hangul Jamo Extended-B
)


def strip_speaker_prefix(line: str) -> str:
    return SPEAKER_PREFIX_RE.sub("", line).strip()


def is_hangul(char: str) -> bool:
    codepoint = ord(char)
    return any(start <= codepoint <= end for start, end in HANGUL_RANGES)


def count_line_breaks(value: str) -> int:
    return sum(1 for _ in LINE_BREAK_RE.finditer(value))


def split_text_lines(value: str) -> list[str]:
    return [line.strip() for line in LINE_BREAK_RE.split(value) if line.strip()]


def normalize_metric_lines(value: Any, *, strip_speakers: bool = True) -> tuple[list[str], int]:
    """Normalize string/list/dict inputs into physical lines plus break count."""

    raw_items: list[str] = []
    if isinstance(value, str):
        raw_items = [value]
    elif isinstance(value, list):
        for item in value:
            if isinstance(item, str):
                raw_items.append(item)
            elif isinstance(item, dict):
                raw_items.append(
                    str(item.get("line") or item.get("text") or item.get("content") or "")
                )
            else:
                raw_items.append(str(item))
    elif isinstance(value, dict):
        raw_items = [str(value.get("line") or value.get("text") or value.get("content") or "")]
    else:
        raw_items = []

    line_breaks = sum(count_line_breaks(item) for item in raw_items)
    lines: list[str] = []
    for item in raw_items:
        for line in split_text_lines(item):
            lines.append(strip_speaker_prefix(line) if strip_speakers else line.strip())
    return lines, line_breaks


def neis_byte_len(value: str) -> int:
    """Approximate NEIS-style byte counting.

    Hangul codepoints count as 3 bytes, ASCII as 1 byte, line breaks as 2 bytes,
    and other codepoints fall back to their UTF-8 encoded length.
    """

    total = 0
    index = 0
    while index < len(value):
        if value.startswith("\r\n", index):
            total += 2
            index += 2
            continue

        char = value[index]
        if char in {"\r", "\n", "\u2028", "\u2029"}:
            total += 2
        elif ord(char) <= 0x7F:
            total += 1
        elif is_hangul(char):
            total += 3
        else:
            total += len(char.encode("utf-8"))
        index += 1
    return total


def line_metrics(line: str, line_index: int) -> dict[str, int]:
    normalized = unicodedata.normalize("NFC", line)
    return {
        "line_index": line_index,
        "nfc_chars": len(normalized),
        "chars_without_whitespace": sum(1 for char in normalized if not char.isspace()),
        "utf8_bytes": len(normalized.encode("utf-8")),
        "neis_bytes": neis_byte_len(normalized),
    }


def average(total: int, count: int) -> float:
    return round(total / count, 1) if count else 0.0


def build_text_metrics(value: Any, *, strip_speakers: bool = True) -> dict[str, Any]:
    lines, line_breaks = normalize_metric_lines(value, strip_speakers=strip_speakers)
    per_line = [line_metrics(line, index) for index, line in enumerate(lines, 1)]
    line_count = len(per_line)

    total_nfc_chars = sum(item["nfc_chars"] for item in per_line)
    total_chars_without_whitespace = sum(item["chars_without_whitespace"] for item in per_line)
    total_utf8_bytes = sum(item["utf8_bytes"] for item in per_line)
    total_neis_bytes = sum(item["neis_bytes"] for item in per_line) + (line_breaks * 2)

    return {
        "schema": "text_metrics",
        "version": VERSION,
        "basis": {
            "stored_text": False,
            "source_text_values": "omitted",
            "normalization": "NFC",
            "line_break_rule": "CRLF, LF, CR, U+2028, and U+2029; CRLF counts once",
        },
        "line_count": line_count,
        "line_breaks": line_breaks,
        "total_nfc_chars": total_nfc_chars,
        "avg_nfc_chars": average(total_nfc_chars, line_count),
        "max_nfc_chars": max((item["nfc_chars"] for item in per_line), default=0),
        "total_chars_without_whitespace": total_chars_without_whitespace,
        "avg_chars_without_whitespace": average(total_chars_without_whitespace, line_count),
        "max_chars_without_whitespace": max(
            (item["chars_without_whitespace"] for item in per_line), default=0
        ),
        "total_utf8_bytes": total_utf8_bytes,
        "avg_utf8_bytes": average(total_utf8_bytes, line_count),
        "max_utf8_bytes": max((item["utf8_bytes"] for item in per_line), default=0),
        "total_neis_bytes": total_neis_bytes,
        "avg_neis_bytes": average(total_neis_bytes, line_count),
        "max_neis_bytes": max((item["neis_bytes"] for item in per_line), default=0),
        "per_line": per_line,
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build source-text-free text metrics.")
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--text", help="Text to inspect. Line breaks are counted.")
    group.add_argument("--lines", help="Dialogue lines to inspect. Newlines are treated as turns.")
    parser.add_argument(
        "--keep-speakers",
        action="store_true",
        help="Include speaker prefixes in metrics instead of stripping 'Speaker:'.",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    value = args.text if args.text is not None else args.lines
    metrics = build_text_metrics(value or "", strip_speakers=not args.keep_speakers)
    print(json.dumps(metrics, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
