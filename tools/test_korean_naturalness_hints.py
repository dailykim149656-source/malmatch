#!/usr/bin/env python3
"""Focused tests for source-text-free Korean naturalness hints."""

from __future__ import annotations

import json

from korean_naturalness_hints import build_korean_naturalness_hints


def test_translationese_and_grammar_hints() -> None:
    lines = [
        "A: 저는 그것은 좋은 결정이라고 생각합니다.",
        "B: 좋은 시간을 보내.",
        "C: 결정을 만들자.",
        "D: 그리고 그리고 바로 움직이자.",
    ]
    result = build_korean_naturalness_hints(lines)

    axes = {hint["axis"] for hint in result["hints"]}
    assert "grammar_acceptability" in axes
    assert "native_korean_idiom" in axes
    assert result["basis"]["stored_text"] is False
    assert result["input_metrics"]["line_count"] == 4
    assert result["input_metrics"]["text_metrics"]["schema"] == "text_metrics"

    serialized = json.dumps(result, ensure_ascii=False)
    for source_fragment in ["그것은 좋은 결정", "좋은 시간을 보내", "결정을 만들자"]:
        assert source_fragment not in serialized


def test_spoken_rhythm_hint() -> None:
    lines = [
        "A: 현재 상황은 매우 복잡한 것으로 보인다.",
        "B: 우리는 이 문제를 신중하게 검토해야 할 것이다.",
        "A: 그것은 중요한 결정이라고 생각한다.",
        "B: 따라서 다음 행동을 선택할 필요가 있다.",
    ]
    result = build_korean_naturalness_hints(lines)

    axes = {hint["axis"] for hint in result["hints"]}
    assert "spoken_korean_rhythm" in axes
    assert result["input_metrics"]["short_reaction_count"] == 0
    assert result["input_metrics"]["written_sentence_count"] >= 3


def test_common_grammar_error_hints() -> None:
    lines = [
        "A: 이제 되요?",
        "B: 어떻해, 몇일 시간이 없잖아.",
        "A: 아니예요, 제가 갈려고 했습니다요.",
        "B: 오늘 할께. 그럼 수있어.",
        "C: 웬지 안되겠어. 하고있어.",
        "D: 못해 본 것같아. 갈 줄알았어.",
    ]
    result = build_korean_naturalness_hints(lines)

    grammar_hints = [
        hint for hint in result["hints"] if hint["axis"] == "grammar_acceptability"
    ]
    assert grammar_hints
    signals = set(grammar_hints[0]["signals"])
    assert "doe_dwae_confusion" in signals
    assert "eotteokhae_misspelling" in signals
    assert "anieyo_misspelling" in signals
    assert "intent_l_euryeogo" in signals
    assert "nonstandard_polite_ending" in signals
    assert "halge_misspelling" in signals
    assert "bound_noun_spacing" in signals
    assert "waen_wen_confusion" in signals
    assert "an_dwae_spacing" in signals
    assert "mot_spacing_suspect" in signals
    assert "bound_noun_spacing_expanded" in signals
    assert "auxiliary_spacing_suspect" in signals
    assert "doe_dwae_confusion" in result["signal_catalog"]
    assert "doe_dwae_confusion" in result["suggestion_catalog"]
    assert "waen_wen_confusion" in result["suggestion_catalog"]

    serialized = json.dumps(result, ensure_ascii=False)
    for source_fragment in ["이제 되요", "어떻해", "갈려고", "수있어", "하고있어"]:
        assert source_fragment not in serialized


def test_common_particle_surface_not_flagged() -> None:
    lines = [
        "A: 종이가 책상 위에 있어.",
        "B: 고양이가 문 앞에 앉아 있어.",
    ]
    result = build_korean_naturalness_hints(lines)

    grammar_hints = [
        hint for hint in result["hints"] if hint["axis"] == "grammar_acceptability"
    ]
    assert not grammar_hints


def main() -> int:
    test_translationese_and_grammar_hints()
    test_spoken_rhythm_hint()
    test_common_grammar_error_hints()
    test_common_particle_surface_not_flagged()
    print("Korean naturalness hint tests passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
