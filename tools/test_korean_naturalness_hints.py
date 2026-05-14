#!/usr/bin/env python3
"""Focused tests for source-text-free Korean naturalness hints."""

from __future__ import annotations

import json

from korean_naturalness_hints import build_korean_naturalness_hints


def test_translationese_and_grammar_hints() -> None:
    lines = [
        "A: 나는은 이것은 좋은 결정이라고 생각한다.",
        "B: 좋은 시간을 보내.",
        "C: 결정을 만들자.",
    ]
    result = build_korean_naturalness_hints(lines)

    axes = {hint["axis"] for hint in result["hints"]}
    assert "grammar_acceptability" in axes
    assert "native_korean_idiom" in axes
    assert result["basis"]["stored_text"] is False
    assert result["input_metrics"]["line_count"] == 3

    serialized = json.dumps(result, ensure_ascii=False)
    for source_fragment in ["나는은", "좋은 시간을 보내", "결정을 만들자"]:
        assert source_fragment not in serialized


def test_spoken_rhythm_hint() -> None:
    lines = [
        "A: 저는 현재 상황에 대해 깊이 고민하고 있습니다.",
        "B: 그것은 우리가 해결해야 하는 문제입니다.",
        "A: 저는 이 결정이 필요하다고 생각합니다.",
        "B: 그것은 매우 중요한 일입니다.",
    ]
    result = build_korean_naturalness_hints(lines)

    axes = {hint["axis"] for hint in result["hints"]}
    assert "spoken_korean_rhythm" in axes
    assert result["input_metrics"]["short_reaction_count"] == 0
    assert result["input_metrics"]["written_sentence_count"] >= 3


def main() -> int:
    test_translationese_and_grammar_hints()
    test_spoken_rhythm_hint()
    print("Korean naturalness hint tests passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
