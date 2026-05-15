#!/usr/bin/env python3
"""Focused tests for deterministic, source-text-free text metrics."""

from __future__ import annotations

import json

from text_metrics import build_text_metrics, neis_byte_len


def test_line_break_contract() -> None:
    result = build_text_metrics("A\r\nB\nC\rD\u2028E\u2029F", strip_speakers=False)

    assert result["schema"] == "text_metrics"
    assert result["line_breaks"] == 5
    assert result["line_count"] == 6
    assert result["basis"]["stored_text"] is False
    assert [item["line_index"] for item in result["per_line"]] == [1, 2, 3, 4, 5, 6]


def test_nfc_and_byte_contract() -> None:
    decomposed = "가A"
    result = build_text_metrics(decomposed, strip_speakers=False)
    item = result["per_line"][0]

    assert item["nfc_chars"] == 2
    assert item["utf8_bytes"] == len("가A".encode("utf-8"))
    assert item["neis_bytes"] == 4
    assert neis_byte_len("가\r\nA") == 6


def test_whitespace_and_source_text_omission() -> None:
    source = "화자: 비공개 원문 조각입니다"
    result = build_text_metrics(source)

    assert result["line_count"] == 1
    assert result["per_line"][0]["chars_without_whitespace"] < result["per_line"][0]["nfc_chars"]

    serialized = json.dumps(result, ensure_ascii=False)
    assert "비공개 원문 조각" not in serialized
    assert "화자:" not in serialized


def main() -> int:
    test_line_break_contract()
    test_nfc_and_byte_contract()
    test_whitespace_and_source_text_omission()
    print("Text metrics tests passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
