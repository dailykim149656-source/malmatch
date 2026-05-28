#!/usr/bin/env python3
"""Focused tests for source-text-free Korean naturalness hints."""

from __future__ import annotations

import json

from korean_naturalness_hints import build_korean_naturalness_hints


def all_signals(result: dict) -> set[str]:
    return {
        signal
        for hint in result["hints"]
        for signal in hint["signals"]
    }


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
    assert result["signal_metadata"]["doe_dwae_confusion"]["category"] == "spelling"
    assert result["signal_metadata"]["honorific_ending_collision"]["severity"] == "high"
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


def test_ai_style_punctuation_and_formulaic_frames() -> None:
    lines = [
        "A: 핵심은 속도가 아니다. 방향이다.",
        "B: 단순히 빨리 가는 게 아니라 같이 가는 거야.",
        "C: 괜찮아 — 지금은 네 말부터 듣자.",
        "D: 결국 중요한 것은 네가 다시 서는 거야.",
    ]
    result = build_korean_naturalness_hints(lines)

    rhythm_hints = [
        hint for hint in result["hints"] if hint["axis"] == "spoken_korean_rhythm"
    ]
    assert rhythm_hints
    signals = {
        signal
        for hint in rhythm_hints
        for signal in hint["signals"]
    }
    assert "em_dash_punctuation" in signals
    assert "formulaic_contrast_frame" in signals
    assert "formulaic_transition_frame" in signals
    assert "em_dash_punctuation" in result["suggestion_catalog"]

    serialized = json.dumps(result, ensure_ascii=False)
    for source_fragment in ["핵심은 속도", "괜찮아", "다시 서는 거야"]:
        assert source_fragment not in serialized


def test_post_editese_translationese_signals() -> None:
    lines = [
        "A: 그녀는 그녀의 선택이 모두에게 영향을 줄 것이라고 말했어요.",
        "B: 이 문제는 위원회에 의해 처리되어진다고 들었어요.",
        "C: 회의에서의 결정은 우리에게 중요한 의미를 가지고 있어요.",
        "D: 데이터는 새로운 결과를 보여주고 있어요.",
    ]
    result = build_korean_naturalness_hints(lines)
    signals = all_signals(result)

    assert "third_person_pronoun_literalism" in signals
    assert "by_passive_literalism" in signals
    assert "double_passive_literalism" in signals
    assert "double_particle_literalism" in signals
    assert "have_make_literalism_expanded" in signals
    assert "progressive_aspect_cluster" in signals
    assert result["input_metrics"]["third_person_pronoun_count"] >= 2
    assert result["input_metrics"]["progressive_aspect_count"] >= 2
    assert "third_person_pronoun_literalism" in result["suggestion_catalog"]
    assert result["signal_metadata"]["third_person_pronoun_literalism"]["scope"] == "scene"
    assert result["signal_metadata"]["double_passive_literalism"]["severity"] == "high"
    assert "double_particle_literalism" in result["signal_catalog"]

    serialized = json.dumps(result, ensure_ascii=False)
    for source_fragment in ["그녀의 선택", "위원회에 의해", "회의에서의 결정", "데이터는 새로운"]:
        assert source_fragment not in serialized


def test_relative_clause_and_discourse_rhythm_signals() -> None:
    lines = [
        "A: 내가 어제 말한 오래 묻혀 있던 네가 놓친 단서를 아는 사람이 왔어.",
        "B: 따라서 우리는 움직인다.",
        "A: 이를 통해 단서를 확인한다.",
        "B: 지금 판단한다.",
        "A: 모두 기록한다.",
    ]
    result = build_korean_naturalness_hints(lines)
    signals = all_signals(result)

    assert "relative_clause_stack" in signals
    assert "ai_discourse_marker_cluster" in signals
    assert "da_ending_streak" in signals
    assert result["input_metrics"]["relative_clause_stack_count"] == 1
    assert result["input_metrics"]["discourse_marker_count"] == 2
    assert result["input_metrics"]["da_ending_streak_line_count"] >= 4

    serialized = json.dumps(result, ensure_ascii=False)
    for source_fragment in ["어제 말한", "묻혀 있던", "움직인다"]:
        assert source_fragment not in serialized


def test_dialogue_safe_post_editese_surfaces_not_overflagged() -> None:
    lines = [
        "A: 그건 네 잘못이 아니야.",
        "B: 나 지금 기다리고 있어.",
        "A: 종이가 책상 위에 있어.",
        "B: 그래, 조금만 더 있어.",
    ]
    result = build_korean_naturalness_hints(lines)
    signals = all_signals(result)

    assert "third_person_pronoun_literalism" not in signals
    assert "progressive_aspect_cluster" not in signals
    assert "double_particle_literalism" not in signals
    assert result["input_metrics"]["progressive_aspect_count"] == 1


def main() -> int:
    test_translationese_and_grammar_hints()
    test_spoken_rhythm_hint()
    test_common_grammar_error_hints()
    test_common_particle_surface_not_flagged()
    test_ai_style_punctuation_and_formulaic_frames()
    test_post_editese_translationese_signals()
    test_relative_clause_and_discourse_rhythm_signals()
    test_dialogue_safe_post_editese_surfaces_not_overflagged()
    print("Korean naturalness hint tests passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
