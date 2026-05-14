#!/usr/bin/env python3
"""Focused tests for source-text-free calibration hints."""

from __future__ import annotations

import json
from pathlib import Path

from calibration_hints import build_calibration_hints


def test_mixed_speech_and_relationship_hints() -> None:
    lines = [
        "A: 고객님, 지금 처리하겠습니다.",
        "B: 야, 너 진짜 운명이야.",
        "C: 이 문제는 제가 다 해결해 드릴게요.",
    ]
    result = build_calibration_hints(
        lines,
        profile_path=Path("missing-profile.json"),
        scene="고객 응대 중 처음 만난 상황",
        relationship_boundaries="초면, 공식, 고객",
    )

    axes = {hint["axis"] for hint in result["hints"]}
    assert "speech_level_consistency" in axes
    assert "relationship_fit" in axes
    assert result["basis"]["stored_text"] is False
    assert result["basis"]["profile_source"] == "built_in_defaults"
    assert result["input_metrics"]["line_count"] == 3

    serialized = json.dumps(result, ensure_ascii=False)
    for source_fragment in ["고객님", "운명이야", "해결해 드릴게요"]:
        assert source_fragment not in serialized


def test_length_and_anachronism_hints() -> None:
    long_line = "A: " + "설명을 계속 이어 가는 문장입니다. " * 12
    result = build_calibration_hints(
        [long_line, "B: 카톡으로 보내면 되지."],
        profile_path=Path("missing-profile.json"),
        genre="조선 사극",
    )

    axes = {hint["axis"] for hint in result["hints"]}
    assert "naturalness" in axes
    assert "genre_fit" in axes
    assert "anachronism_risk" in axes
    assert result["input_metrics"]["max_chars"] > result["thresholds"]["hard_max_chars"]


def test_korean_politeness_context_hints() -> None:
    lines = [
        "A: 안됩니다.",
        "B: 기다려.",
        "A: 빨리 서류 보내세요.",
    ]
    result = build_calibration_hints(
        lines,
        profile_path=Path("missing-profile.json"),
        scene="고객이 환불을 요구하며 항의하는 상황",
        relationship_boundaries="초면, 공식, 고객, 민원",
    )

    relationship_hints = [
        hint for hint in result["hints"] if hint["axis"] == "relationship_fit"
    ]
    signals = {signal for hint in relationship_hints for signal in hint["signals"]}
    assert "direct_command_in_polite_context" in signals
    assert "unsoftened_request_in_polite_context" in signals
    assert "blunt_refusal_without_buffer" in signals
    assert "missing_apology_or_acknowledgement_in_service_context" in signals
    assert "direct_command_in_polite_context" in result["signal_catalog"]

    serialized = json.dumps(result, ensure_ascii=False)
    for source_fragment in ["안됩니다", "기다려", "서류 보내세요"]:
        assert source_fragment not in serialized


def test_buffered_polite_request_not_flagged() -> None:
    lines = [
        "A: 고객님, 죄송하지만 잠시만 기다려 주시겠어요?",
        "B: 확인해 주셔서 감사합니다.",
    ]
    result = build_calibration_hints(
        lines,
        profile_path=Path("missing-profile.json"),
        scene="고객 문의를 처리하는 상황",
        relationship_boundaries="초면, 공식, 고객",
    )

    signals = {
        signal
        for hint in result["hints"]
        if hint["axis"] == "relationship_fit"
        for signal in hint["signals"]
    }
    assert "direct_command_in_polite_context" not in signals
    assert "unsoftened_request_in_polite_context" not in signals
    assert "blunt_refusal_without_buffer" not in signals
    assert "missing_apology_or_acknowledgement_in_service_context" not in signals


def main() -> int:
    test_mixed_speech_and_relationship_hints()
    test_length_and_anachronism_hints()
    test_korean_politeness_context_hints()
    test_buffered_polite_request_not_flagged()
    print("Calibration hint tests passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
